package engine

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/bala/tradedesk-watcher/internal/alerts"
	"github.com/bala/tradedesk-watcher/internal/config"
	"github.com/bala/tradedesk-watcher/internal/metrics"
	"github.com/bala/tradedesk-watcher/internal/position"
	"github.com/bala/tradedesk-watcher/internal/tvconn"
)

// Watcher watches a single ticker goroutine.
type Watcher struct {
	pos       position.Position
	cfg       *config.Settings
	events    chan<- Event
	cmdCh     chan Command
	state     WatcherState
	price     float64
	prevPrice float64
	vwap      *metrics.VWAP
	rsi       *metrics.RSI
	ema9      *metrics.EMA
	cooldown  *alerts.CooldownTracker
	ratelimit *alerts.RateLimiter
}

// NewWatcher creates a new watcher for a position.
func NewWatcher(pos position.Position, cfg *config.Settings, events chan<- Event) *Watcher {
	return &Watcher{
		pos:       pos,
		cfg:       cfg,
		events:    events,
		cmdCh:     make(chan Command, 10),
		state:     StateStarting,
		vwap:      metrics.NewVWAP(),
		rsi:       metrics.NewRSI(14),
		ema9:      metrics.NewEMA(9),
		cooldown:  alerts.NewCooldownTracker(),
		ratelimit: alerts.NewRateLimiter(5),
	}
}

// Commands returns the channel for sending commands to this watcher.
func (w *Watcher) Commands() chan<- Command {
	return w.cmdCh
}

// Run starts the watcher loop. Blocks until ctx is cancelled or stopped.
func (w *Watcher) Run(ctx context.Context) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[watcher:%s] panic recovered: %v", w.pos.Ticker, r)
			w.events <- Event{
				Type:   EventPanic,
				Ticker: w.pos.Ticker,
				Error:  r,
				Time:   time.Now(),
			}
		}
	}()

	authToken, err := config.LoadAuthToken(w.cfg.SecretsDir)
	if err != nil {
		w.emitState(StateFailed, fmt.Sprintf("auth: %v", err))
		return
	}

	exchange := w.pos.Exchange
	if exchange == "" {
		exchange = "NASDAQ"
	}

	conn, err := tvconn.Connect(authToken)
	if err != nil {
		w.emitState(StateFailed, fmt.Sprintf("connect: %v", err))
		return
	}
	defer conn.Close()

	if err := conn.Subscribe(w.pos.Ticker, exchange, 390); err != nil {
		w.emitState(StateFailed, fmt.Sprintf("subscribe: %v", err))
		return
	}

	go conn.ReadLoop()

	w.state = StateRunning
	w.emitState(StateRunning, fmt.Sprintf("👁️ Watching %s @ %s", w.pos.Ticker, exchange))

	for {
		select {
		case <-ctx.Done():
			w.emitState(StateStopped, "context cancelled")
			return

		case cmd := <-w.cmdCh:
			w.handleCommand(cmd)
			if w.state == StateStopped {
				return
			}

		case bar := <-conn.Bars():
			if len(bar.Bars) == 0 {
				continue
			}
			b := bar.Bars[len(bar.Bars)-1]
			w.vwap.Update(b.High, b.Low, b.Close, b.Volume)
			w.rsi.Update(b.Close)
			w.ema9.Update(b.Close)
			w.prevPrice = w.price
			w.price = b.Close

			w.events <- Event{
				Type:    EventPriceUpdate,
				Ticker:  w.pos.Ticker,
				Price:   b.Close,
				VWAP:    w.vwap.Value(),
				RSI:     w.rsi.Value(),
				Message: w.formatUpdate(b.Close),
				Time:    time.Now(),
			}

			w.checkAlerts(b.Close)

		case err := <-conn.Errors():
			log.Printf("[watcher:%s] connection error: %v — reconnecting", w.pos.Ticker, err)
			return // supervisor will restart

		case <-conn.Done():
			log.Printf("[watcher:%s] connection closed — reconnecting", w.pos.Ticker)
			return
		}
	}
}

func (w *Watcher) handleCommand(cmd Command) {
	switch cmd.Type {
	case CmdStop:
		w.state = StateStopped
		if cmd.Reply != nil {
			cmd.Reply <- CommandReply{State: StateStopped, Message: "stopped"}
		}
	case CmdPause:
		w.state = StatePaused
		if cmd.Reply != nil {
			cmd.Reply <- CommandReply{State: StatePaused, Message: "paused"}
		}
	case CmdResume:
		w.state = StateRunning
		if cmd.Reply != nil {
			cmd.Reply <- CommandReply{State: StateRunning, Message: "resumed"}
		}
	case CmdStatus:
		if cmd.Reply != nil {
			cmd.Reply <- CommandReply{
				State:   w.state,
				Price:   w.price,
				VWAP:    w.vwap.Value(),
				RSI:     w.rsi.Value(),
				PnL:     w.pos.PnLDollars(w.price),
				Message: w.formatUpdate(w.price),
			}
		}
	case CmdUpdateLevels:
		if cmd.Stop > 0 {
			w.pos.Stop = cmd.Stop
		}
		if cmd.Target > 0 {
			w.pos.Target = cmd.Target
		}
		if cmd.Reply != nil {
			cmd.Reply <- CommandReply{State: w.state, Message: fmt.Sprintf("updated stop=%.2f target=%.2f", w.pos.Stop, w.pos.Target)}
		}
	}
}

func (w *Watcher) checkAlerts(price float64) {
	if w.state == StatePaused {
		return
	}
	cooldown := time.Duration(w.cfg.AlertCooldownMins) * time.Minute

	candidates := []*alerts.Alert{
		alerts.CheckStopHit(w.pos.Ticker, price, &w.pos),
		alerts.CheckTargetHit(w.pos.Ticker, price, &w.pos),
		alerts.CheckNearStop(w.pos.Ticker, price, &w.pos, 1.5),
		alerts.CheckVWAPBreak(w.pos.Ticker, price, w.prevPrice, w.vwap.Value()),
		alerts.CheckVWAPReclaim(w.pos.Ticker, price, w.prevPrice, w.vwap.Value()),
		alerts.CheckFlashMove(w.pos.Ticker, price, w.prevPrice, 1.5),
	}

	for _, a := range candidates {
		if a == nil {
			continue
		}
		if !w.cooldown.CanAlert(w.pos.Ticker, a.Type, cooldown) {
			continue
		}
		if !w.ratelimit.Allow(a.Severity) {
			continue
		}
		w.cooldown.Record(w.pos.Ticker, a.Type)
		w.events <- Event{
			Type:    EventAlert,
			Ticker:  w.pos.Ticker,
			Price:   price,
			VWAP:    w.vwap.Value(),
			RSI:     w.rsi.Value(),
			Message: a.Message,
			Time:    time.Now(),
		}
	}
}

func (w *Watcher) formatUpdate(price float64) string {
	pnl := w.pos.PnLDollars(price)
	sign := "+"
	if pnl < 0 {
		sign = ""
	}
	return fmt.Sprintf("%s $%.2f | VWAP $%.2f | RSI %.1f | P&L %s$%.0f",
		w.pos.Ticker, price, w.vwap.Value(), w.rsi.Value(), sign, pnl)
}

func (w *Watcher) emitState(s WatcherState, msg string) {
	w.state = s
	w.events <- Event{
		Type:    EventStateChange,
		Ticker:  w.pos.Ticker,
		State:   s,
		Message: msg,
		Time:    time.Now(),
	}
}
