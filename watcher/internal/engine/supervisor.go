package engine

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"sync"
	"time"

	"github.com/bala/tradedesk-watcher/internal/config"
	"github.com/bala/tradedesk-watcher/internal/position"
)

const (
	maxRestartsPerHour = 3
	restartDelay       = 5 * time.Second
)

// Supervisor manages multiple watcher goroutines.
type Supervisor struct {
	cfg      *config.Settings
	registry *Registry
	watchers map[string]*Watcher
	events   chan Event
	mu       sync.RWMutex
	ctx      context.Context
	cancel   context.CancelFunc
	silenced bool // global alert mute
}

// NewSupervisor creates a new supervisor.
func NewSupervisor(cfg *config.Settings, registryPath string) *Supervisor {
	ctx, cancel := context.WithCancel(context.Background())
	return &Supervisor{
		cfg:      cfg,
		registry: NewRegistry(registryPath),
		watchers: make(map[string]*Watcher),
		events:   make(chan Event, 100),
		ctx:      ctx,
		cancel:   cancel,
	}
}

// Events returns the channel for receiving events from all watchers.
func (s *Supervisor) Events() <-chan Event {
	return s.events
}

// Start launches watchers for all given positions.
func (s *Supervisor) Start(positions []position.Position) {
	for _, pos := range positions {
		s.StartWatcher(pos)
	}
	go s.healthLoop()
}

// StartWatcher starts a new watcher goroutine for a position.
func (s *Supervisor) StartWatcher(pos position.Position) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.watchers[pos.Ticker]; exists {
		log.Printf("[supervisor] watcher for %s already running", pos.Ticker)
		return
	}

	w := NewWatcher(pos, s.cfg, s.events, s.registry)
	s.watchers[pos.Ticker] = w

	s.registry.Register(pos.Ticker, &RegistryEntry{
		Ticker:    pos.Ticker,
		State:     StateRunning.String(),
		StartedAt: time.Now(),
		Stop:      pos.Stop,
		Target:    pos.Target,
		AvgPrice:  pos.AvgPrice,
	})

	go s.runWithRestart(pos, w)
	log.Printf("[supervisor] started watcher for %s", pos.Ticker)
}

// StopWatcher stops the watcher for a ticker.
func (s *Supervisor) StopWatcher(ticker string) {
	s.mu.Lock()
	w, ok := s.watchers[ticker]
	if !ok {
		s.mu.Unlock()
		return
	}
	delete(s.watchers, ticker)
	s.mu.Unlock()

	reply := make(chan CommandReply, 1)
	w.Commands() <- Command{Type: CmdStop, Reply: reply}
	select {
	case <-reply:
	case <-time.After(3 * time.Second):
	}
	s.registry.Remove(ticker)
	log.Printf("[supervisor] stopped watcher for %s", ticker)
}

// SendCommand sends a command to a specific watcher.
func (s *Supervisor) SendCommand(ticker string, cmd Command) (CommandReply, bool) {
	s.mu.RLock()
	w, ok := s.watchers[ticker]
	s.mu.RUnlock()
	if !ok {
		return CommandReply{Error: "watcher not found"}, false
	}
	reply := make(chan CommandReply, 1)
	cmd.Reply = reply
	w.Commands() <- cmd
	select {
	case r := <-reply:
		return r, true
	case <-time.After(3 * time.Second):
		return CommandReply{Error: "timeout"}, false
	}
}

// ListWatchers returns the registry entries for all watchers.
func (s *Supervisor) ListWatchers() map[string]*RegistryEntry {
	return s.registry.List()
}

// Stop shuts down all watchers.
func (s *Supervisor) Stop() {
	s.cancel()
	s.mu.RLock()
	tickers := make([]string, 0, len(s.watchers))
	for t := range s.watchers {
		tickers = append(tickers, t)
	}
	s.mu.RUnlock()
	for _, t := range tickers {
		s.StopWatcher(t)
	}
}

func (s *Supervisor) runWithRestart(pos position.Position, w *Watcher) {
	restarts := 0
	lastReset := time.Now()

	for {
		wCtx, wCancel := context.WithCancel(s.ctx)
		go func() {
			defer wCancel()
			w.Run(wCtx)
		}()

		// Wait for watcher to exit
		<-wCtx.Done()

		// Check if supervisor is shutting down
		select {
		case <-s.ctx.Done():
			return
		default:
		}

		// Reset restart counter hourly
		if time.Since(lastReset) > time.Hour {
			restarts = 0
			lastReset = time.Now()
		}

		restarts++
		s.registry.IncrementRestarts(pos.Ticker)

		if restarts > maxRestartsPerHour {
			log.Printf("[supervisor] %s exceeded max restarts (%d/hr) — stopping", pos.Ticker, maxRestartsPerHour)
			s.events <- Event{
				Type:    EventAlert,
				Ticker:  pos.Ticker,
				Message: "⚠️ " + pos.Ticker + " watcher failed too many times — stopped",
				Time:    time.Now(),
			}
			s.mu.Lock()
			delete(s.watchers, pos.Ticker)
			s.mu.Unlock()
			s.registry.Remove(pos.Ticker)
			return
		}

		log.Printf("[supervisor] restarting %s watcher in %v (restart %d/%d)", pos.Ticker, restartDelay, restarts, maxRestartsPerHour)
		time.Sleep(restartDelay)

		// Create fresh watcher
		w = NewWatcher(pos, s.cfg, s.events, s.registry)
		s.mu.Lock()
		s.watchers[pos.Ticker] = w
		s.mu.Unlock()
	}
}

func (s *Supervisor) healthLoop() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-s.ctx.Done():
			return
		case <-ticker.C:
			s.mu.RLock()
			count := len(s.watchers)
			s.mu.RUnlock()
			log.Printf("[supervisor] health: %d watchers active", count)
		}
	}
}

// Silence mutes all Telegram alerts globally and persists state.
func (s *Supervisor) Silence() {
	s.mu.Lock()
	s.silenced = true
	s.mu.Unlock()
	s.persistSilence(true)
}

// Unsilence re-enables all Telegram alerts and persists state.
func (s *Supervisor) Unsilence() {
	s.mu.Lock()
	s.silenced = false
	s.mu.Unlock()
	s.persistSilence(false)
}

// IsSilenced returns true if alerts are globally muted.
func (s *Supervisor) IsSilenced() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.silenced
}

// LoadSilenceState loads persisted silence state from disk on startup.
func (s *Supervisor) LoadSilenceState() {
	path := s.cfg.DataDir + "/watcher-state.json"
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	var state struct {
		Silenced bool `json:"silenced"`
	}
	if json.Unmarshal(data, &state) == nil {
		s.mu.Lock()
		s.silenced = state.Silenced
		s.mu.Unlock()
		if state.Silenced {
			log.Printf("[supervisor] alerts silenced (persisted state)")
		}
	}
}

func (s *Supervisor) persistSilence(silenced bool) {
	path := s.cfg.DataDir + "/watcher-state.json"
	data, _ := json.Marshal(map[string]bool{"silenced": silenced})
	tmp := path + ".tmp"
	os.WriteFile(tmp, data, 0644)
	os.Rename(tmp, path)
}
