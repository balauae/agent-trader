package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/bala/tradedesk-watcher/internal/engine"
	"github.com/bala/tradedesk-watcher/internal/position"
)

// Server is the HTTP-over-Unix-socket manager API.
type Server struct {
	socketPath    string
	supervisor    *engine.Supervisor
	positionsFile string // path to positions.json for persistence
	startedAt     time.Time
	server        *http.Server
}

// New creates a new API server.
func New(socketPath string, supervisor *engine.Supervisor) *Server {
	return &Server{
		socketPath: socketPath,
		supervisor: supervisor,
		startedAt:  time.Now(),
	}
}

// SetPositionsFile sets the path used for /watch and /stop persistence.
func (s *Server) SetPositionsFile(path string) {
	s.positionsFile = path
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
	mux.HandleFunc("/analyze/", s.handleAnalyzeTicker)
	mux.HandleFunc("/analyze", s.handleAnalyzeAll)
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

	// Persist to positions.json so it survives restart
	if s.positionsFile != "" {
		if err := position.AddPosition(s.positionsFile, pos); err != nil {
			log.Printf("[api] warning: failed to persist position %s: %v", req.Ticker, err)
		}
	}

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

	// Remove from positions.json
	if s.positionsFile != "" {
		if err := position.RemovePosition(s.positionsFile, ticker); err != nil {
			log.Printf("[api] warning: failed to remove position %s: %v", ticker, err)
		}
	}

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

// GET /analyze/{ticker} — full technical analysis for one ticker
func (s *Server) handleAnalyzeTicker(w http.ResponseWriter, r *http.Request) {
	ticker := strings.TrimPrefix(r.URL.Path, "/analyze/")
	ticker = strings.ToUpper(strings.TrimSpace(ticker))
	if ticker == "" {
		writeError(w, "ticker required", http.StatusBadRequest)
		return
	}

	entries := s.supervisor.ListWatchers()
	e, ok := entries[ticker]
	if !ok {
		writeError(w, fmt.Sprintf("ticker %s not being watched", ticker), http.StatusNotFound)
		return
	}

	writeJSON(w, buildAnalysis(e))
}

// GET /analyze — analysis for all watched tickers
func (s *Server) handleAnalyzeAll(w http.ResponseWriter, r *http.Request) {
	entries := s.supervisor.ListWatchers()
	results := make([]AnalyzeResponse, 0, len(entries))
	for _, e := range entries {
		results = append(results, buildAnalysis(e))
	}
	writeJSON(w, results)
}

// buildAnalysis constructs the full AnalyzeResponse from a registry entry.
func buildAnalysis(e *engine.RegistryEntry) AnalyzeResponse {
	signals := generateSignals(e)
	bias, score := computeBias(signals)

	var sma50 *float64
	if e.BarCount >= 50 && e.SMA50 > 0 {
		v := e.SMA50
		sma50 = &v
	}

	priceVsVWAP := "ABOVE"
	if e.Price < e.VWAP {
		priceVsVWAP = "BELOW"
	}
	distPct := 0.0
	if e.VWAP > 0 {
		distPct = math.Abs(e.Price-e.VWAP) / e.VWAP * 100
	}

	return AnalyzeResponse{
		Ticker:          e.Ticker,
		Timeframe:       "realtime",
		Price:           e.Price,
		Bias:            bias,
		ConfluenceScore: score,
		Indicators: AnalyzeIndicators{
			Close:       e.Price,
			EMA9:        e.EMA9,
			EMA21:       e.EMA21,
			SMA50:       sma50,
			SMA200:      nil, // not enough bars for SMA200 in intraday
			MACDLine:    e.MACD,
			MACDSignal:  e.MACDSignal,
			MACDHist:    e.MACDHist,
			RSI:         e.RSI,
			BBUpper:     e.BBUpper,
			BBMid:       e.BBMid,
			BBLower:     e.BBLower,
			ATR:         e.ATR,
			VWAP:        e.VWAP,
			Volume:      e.Volume,
			VolumeSMA20: e.VolAvg,
			VolAboveAvg: e.VolAboveAvg,
		},
		Levels: AnalyzeLevels{
			Support:    e.Support,
			Resistance: e.Resistance,
			EMA9:       e.EMA9,
			EMA21:      e.EMA21,
			BBUpper:    e.BBUpper,
			BBLower:    e.BBLower,
		},
		Signals: signalTexts(signals),
		VWAP: AnalyzeVWAP{
			Value:       e.VWAP,
			Upper1S:     e.VWAPUpper1,
			Upper2S:     e.VWAPUpper2,
			Lower1S:     e.VWAPLower1,
			Lower2S:     e.VWAPLower2,
			PriceVsVWAP: priceVsVWAP,
			DistancePct: math.Round(distPct*100) / 100,
		},
	}
}

type signal struct {
	text    string
	bullish bool // true=bullish, false=bearish
}

func generateSignals(e *engine.RegistryEntry) []signal {
	var sigs []signal

	// EMA crossover
	if e.EMA9 > 0 && e.EMA21 > 0 {
		if e.EMA9 > e.EMA21 {
			sigs = append(sigs, signal{"EMA9 above EMA21 — short-term bullish", true})
		} else {
			sigs = append(sigs, signal{"EMA9 below EMA21 — short-term bearish", false})
		}
	}

	// MACD histogram
	if e.MACDHist != 0 {
		if e.MACDHist > 0 {
			sigs = append(sigs, signal{"MACD histogram positive — bullish momentum", true})
		} else {
			sigs = append(sigs, signal{"MACD histogram negative — bearish momentum", false})
		}
	}

	// RSI
	if e.RSI > 0 {
		switch {
		case e.RSI > 70:
			sigs = append(sigs, signal{fmt.Sprintf("RSI %.1f — overbought", e.RSI), false})
		case e.RSI >= 55:
			sigs = append(sigs, signal{fmt.Sprintf("RSI %.1f — bullish zone", e.RSI), true})
		case e.RSI < 30:
			sigs = append(sigs, signal{fmt.Sprintf("RSI %.1f — oversold", e.RSI), true})
		case e.RSI <= 45:
			sigs = append(sigs, signal{fmt.Sprintf("RSI %.1f — bearish zone", e.RSI), false})
		}
		// 45-55 is neutral, no signal
	}

	// Price vs VWAP
	if e.VWAP > 0 {
		if e.Price > e.VWAP {
			sigs = append(sigs, signal{"Price above VWAP — intraday strength", true})
		} else {
			sigs = append(sigs, signal{"Price below VWAP — intraday weakness", false})
		}
	}

	// Volume
	if e.VolAboveAvg {
		sigs = append(sigs, signal{"Volume above 20-SMA — confirming move", true})
	}

	// Bollinger Band extremes
	if e.BBLower > 0 && e.BBUpper > 0 {
		bbRange := e.BBUpper - e.BBLower
		if bbRange > 0 {
			if e.Price <= e.BBLower+bbRange*0.05 {
				sigs = append(sigs, signal{"Price at BB lower — possible support / oversold", true})
			} else if e.Price >= e.BBUpper-bbRange*0.05 {
				sigs = append(sigs, signal{"Price at BB upper — possible resistance / overbought", false})
			}
		}
	}

	return sigs
}

func computeBias(sigs []signal) (string, string) {
	bullish := 0
	bearish := 0
	for _, s := range sigs {
		if s.bullish {
			bullish++
		} else {
			bearish++
		}
	}
	total := bullish + bearish
	if total == 0 {
		return "NEUTRAL", "0/0"
	}

	bias := "NEUTRAL"
	confluent := 0
	if bullish >= 3 {
		bias = "BULLISH"
		confluent = bullish
	} else if bearish >= 3 {
		bias = "BEARISH"
		confluent = bearish
	} else {
		// pick the larger side for score
		if bullish > bearish {
			confluent = bullish
		} else {
			confluent = bearish
		}
	}
	return bias, fmt.Sprintf("%d/%d", confluent, total)
}

func signalTexts(sigs []signal) []string {
	out := make([]string, len(sigs))
	for i, s := range sigs {
		out[i] = s.text
	}
	return out
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
