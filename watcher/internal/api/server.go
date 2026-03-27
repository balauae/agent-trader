package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/bala/tradedesk-watcher/internal/engine"
	"github.com/bala/tradedesk-watcher/internal/position"
)

// Server is the HTTP-over-Unix-socket manager API.
type Server struct {
	socketPath string
	supervisor *engine.Supervisor
	startedAt  time.Time
	server     *http.Server
}

// New creates a new API server.
func New(socketPath string, supervisor *engine.Supervisor) *Server {
	return &Server{
		socketPath: socketPath,
		supervisor: supervisor,
		startedAt:  time.Now(),
	}
}

// Start begins listening on the Unix socket.
func (s *Server) Start() error {
	// Clean up stale socket
	os.Remove(s.socketPath)
	if err := os.MkdirAll(filepath.Dir(s.socketPath), 0755); err != nil {
		return fmt.Errorf("api: mkdir: %w", err)
	}

	ln, err := net.Listen("unix", s.socketPath)
	if err != nil {
		return fmt.Errorf("api: listen: %w", err)
	}
	os.Chmod(s.socketPath, 0660)

	mux := http.NewServeMux()
	mux.HandleFunc("/watch", s.handleWatch)
	mux.HandleFunc("/status", s.handleAllStatus)
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/silence", s.handleSilence)
	mux.HandleFunc("/unsilence", s.handleUnsilence)
	// Dynamic routes for ticker-specific ops
	mux.HandleFunc("/stop/", s.handleStop)
	mux.HandleFunc("/update/", s.handleUpdate)
	mux.HandleFunc("/pause/", s.handlePause)

	s.server = &http.Server{Handler: mux}
	log.Printf("[api] listening on %s", s.socketPath)
	go s.server.Serve(ln)
	return nil
}

// Shutdown gracefully stops the server.
func (s *Server) Shutdown(ctx context.Context) error {
	if s.server != nil {
		return s.server.Shutdown(ctx)
	}
	return nil
}

// POST /watch — start watching a ticker
func (s *Server) handleWatch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req WatchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "invalid request: "+err.Error(), http.StatusBadRequest)
		return
	}
	if req.Ticker == "" {
		writeError(w, "ticker required", http.StatusBadRequest)
		return
	}

	pos := position.Position{
		Ticker:   req.Ticker,
		Exchange: req.Exchange,
		Shares:   req.Shares,
		AvgPrice: req.AvgPrice,
		Stop:     req.Stop,
		Target:   req.Target,
		Dir:      position.Direction(req.Direction),
	}
	if pos.Dir == "" {
		pos.Dir = position.Long
	}

	s.supervisor.StartWatcher(pos)
	writeJSON(w, OKResponse{OK: true, Message: fmt.Sprintf("👁️ Watching %s", req.Ticker)})
}

// DELETE /stop/{ticker} — stop watching a ticker
func (s *Server) handleStop(w http.ResponseWriter, r *http.Request) {
	ticker := r.URL.Path[len("/stop/"):]
	if ticker == "" {
		writeError(w, "ticker required", http.StatusBadRequest)
		return
	}
	s.supervisor.StopWatcher(ticker)
	writeJSON(w, OKResponse{OK: true, Message: fmt.Sprintf("Stopped watching %s", ticker)})
}

// GET /status — all watchers status
func (s *Server) handleAllStatus(w http.ResponseWriter, r *http.Request) {
	entries := s.supervisor.ListWatchers()
	var statuses []StatusResponse
	for ticker, e := range entries {
		statuses = append(statuses, StatusResponse{
			Ticker:        ticker,
			State:         e.State,
			Price:         e.Price,
			VWAP:          e.VWAP,
			RSI:           e.RSI,
			AvgPrice:      e.AvgPrice,
			PnLDollars:    e.PnLDollars,
			Stop:          e.Stop,
			Target:        e.Target,
			VWAPDistPct:   e.VWAPDistPct,
			StopDistPct:   e.StopDistPct,
			TargetDistPct: e.TargetDistPct,
			StartedAt:     e.StartedAt.Format("15:04:05"),
			Restarts:      e.Restarts,
		})
	}
	writeJSON(w, statuses)
}

// GET /health — system health
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	entries := s.supervisor.ListWatchers()
	uptime := time.Since(s.startedAt).Round(time.Second).String()
	writeJSON(w, HealthResponse{
		Status:       "ok",
		Uptime:       uptime,
		WatcherCount: len(entries),
		Silenced:     s.supervisor.IsSilenced(),
	})
}

// POST /update/{ticker} — update stop/target
func (s *Server) handleUpdate(w http.ResponseWriter, r *http.Request) {
	ticker := r.URL.Path[len("/update/"):]
	if ticker == "" {
		writeError(w, "ticker required", http.StatusBadRequest)
		return
	}
	var req UpdateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "invalid request: "+err.Error(), http.StatusBadRequest)
		return
	}
	reply, ok := s.supervisor.SendCommand(ticker, engine.Command{
		Type:   engine.CmdUpdateLevels,
		Stop:   req.Stop,
		Target: req.Target,
	})
	if !ok {
		writeError(w, reply.Error, http.StatusNotFound)
		return
	}
	writeJSON(w, OKResponse{OK: true, Message: reply.Message})
}

// POST /pause/{ticker} — pause alerts
func (s *Server) handlePause(w http.ResponseWriter, r *http.Request) {
	ticker := r.URL.Path[len("/pause/"):]
	if ticker == "" {
		writeError(w, "ticker required", http.StatusBadRequest)
		return
	}
	reply, ok := s.supervisor.SendCommand(ticker, engine.Command{Type: engine.CmdPause})
	if !ok {
		writeError(w, reply.Error, http.StatusNotFound)
		return
	}
	writeJSON(w, OKResponse{OK: true, Message: reply.Message})
}

func writeJSON(w http.ResponseWriter, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(ErrorResponse{Error: msg})
}

// POST /silence — mute all alerts globally
func (s *Server) handleSilence(w http.ResponseWriter, r *http.Request) {
	s.supervisor.Silence()
	writeJSON(w, OKResponse{OK: true, Message: "🔕 Alerts silenced — watching continues"})
}

// POST /unsilence — re-enable all alerts
func (s *Server) handleUnsilence(w http.ResponseWriter, r *http.Request) {
	s.supervisor.Unsilence()
	writeJSON(w, OKResponse{OK: true, Message: "🔔 Alerts resumed"})
}
