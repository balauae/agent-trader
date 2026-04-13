package engine

import (
	"context"
	"fmt"
	"log"
	"math"
	"time"

	"github.com/bala/tradedesk-watcher/internal/alerts"
	"github.com/bala/tradedesk-watcher/internal/bridge"
	"github.com/bala/tradedesk-watcher/internal/config"
	"github.com/bala/tradedesk-watcher/internal/metrics"
	"github.com/bala/tradedesk-watcher/internal/position"
	"github.com/bala/tradedesk-watcher/internal/store"
	"github.com/bala/tradedesk-watcher/internal/tvconn"
)

// Watcher watches a single ticker goroutine.
type Watcher struct {
	pos        position.Position
	cfg        *config.Settings
	events     chan<- Event
	cmdCh      chan Command
	state      WatcherState
	price      float64
	prevPrice  float64
	vwap       *metrics.VWAP
	rsi        *metrics.RSI
	ema9       *metrics.EMA
	ema21      *metrics.EMA
	macd       *metrics.MACD
	atr        *metrics.ATR
	volTracker *metrics.VolumeTracker
	barBuf     *BarBuffer
	cooldown   *alerts.CooldownTracker
	ratelimit  *alerts.RateLimiter
	registry   *Registry
	barStore   *store.BarStore
	srLevels   []float64 // key S/R levels loaded from bridge
}

// NewWatcher creates a new watcher for a position.
func NewWatcher(pos position.Position, cfg *config.Settings, events chan<- Event, registry *Registry, barStore *store.BarStore) *Watcher {
	return &Watcher{
		pos:        pos,
		cfg:        cfg,
		events:     events,
		cmdCh:      make(chan Command, 10),
		state:      StateStarting,
		vwap:       metrics.NewVWAP(),
		rsi:        metrics.NewRSI(14),
		ema9:       metrics.NewEMA(9),
		ema21:      metrics.NewEMA(21),
		macd:       metrics.NewMACD(12, 26, 9),
		atr:        metrics.NewATR(14),
		volTracker: metrics.NewVolumeTracker(20),
		barBuf:     NewBarBuffer(200),
		cooldown:   alerts.NewCooldownTracker(),
		ratelimit:  alerts.NewRateLimiter(5),
		registry:   registry,
		barStore:   barStore,
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

	// Seed metrics from DuckDB historical bars before connecting
	if w.barStore != nil {
		w.seedFromHistory()
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

	// Load S/R levels from bridge (non-blocking, best-effort)
	go w.loadSRLevels()

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
			// Feed ALL bars through metrics (critical for initial 300-bar batch)
			for _, b := range bar.Bars {
				w.vwap.Update(b.High, b.Low, b.Close, b.Volume)
				w.rsi.Update(b.Close)
				w.ema9.Update(b.Close)
				w.ema21.Update(b.Close)
				w.macd.Update(b.Close)
				w.atr.Update(b.High, b.Low, b.Close)
				w.volTracker.Update(b.Volume)
				w.barBuf.Add(Bar{High: b.High, Low: b.Low, Close: b.Close, Volume: b.Volume})
				w.prevPrice = w.price
				w.price = b.Close
			}
			b := bar.Bars[len(bar.Bars)-1]

			// Compute extended metrics from bar buffer
			bbMid, bbUpper, bbLower := w.barBuf.BollingerBands(20, 2.0)
			support, resistance := w.barBuf.SupportResistance(20)
			sma50 := w.barBuf.SMA(50)

			ext := ExtendedMetrics{
				EMA9:        w.ema9.Value(),
				EMA21:       w.ema21.Value(),
				SMA50:       sma50,
				MACD:        w.macd.MACDLine(),
				MACDSignal:  w.macd.Signal(),
				MACDHist:    w.macd.Histogram(),
				ATR:         w.atr.Value(),
				BBUpper:     bbUpper,
				BBLower:     bbLower,
				BBMid:       bbMid,
				Volume:      b.Volume,
				VolAvg:      w.volTracker.Average(),
				VolAboveAvg: w.volTracker.Current() > w.volTracker.Average(),
				Support:     support,
				Resistance:  resistance,
				BarCount:    w.barBuf.Len(),
				VWAPUpper1:  w.vwap.Upper1Sigma(),
				VWAPUpper2:  w.vwap.Upper2Sigma(),
				VWAPLower1:  w.vwap.Lower1Sigma(),
				VWAPLower2:  w.vwap.Lower2Sigma(),
			}

			// push live metrics to registry for API status queries
			if w.registry != nil {
				w.registry.UpdateAllMetrics(
					w.pos.Ticker,
					b.Close, w.vwap.Value(), w.rsi.Value(),
					w.pos.Shares, w.pos.AvgPrice,
					w.pos.Stop, w.pos.Target,
					ext,
				)
			}

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
			w.checkSRProximity(b.Close)

			// Persist live bars to DuckDB (fire-and-forget)
			if w.barStore != nil {
				storeBars := make([]store.Bar, len(bar.Bars))
				for i, tvb := range bar.Bars {
					storeBars[i] = store.Bar{
						Timestamp: tvb.Time,
						Open:      tvb.Open,
						High:      tvb.High,
						Low:       tvb.Low,
						Close:     tvb.Close,
						Volume:    tvb.Volume,
					}
				}
				go func() {
					if err := w.barStore.WriteBars(w.pos.Ticker, "1m", storeBars); err != nil {
						log.Printf("[watcher:%s] duckdb write: %v", w.pos.Ticker, err)
					}
				}()
			}

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
		alerts.CheckRSI(w.pos.Ticker, price, w.rsi.Value()),
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
			Type:      EventAlert,
			AlertType: string(a.Type),
			Ticker:    w.pos.Ticker,
			Price:     price,
			VWAP:      w.vwap.Value(),
			RSI:       w.rsi.Value(),
			PnL:       w.pos.PnLDollars(price),
			Message:   a.Message,
			Time:      time.Now(),
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

// loadSRLevels fetches key S/R levels from the FastAPI bridge.
func (w *Watcher) loadSRLevels() {
	bc := bridge.New(w.cfg.BridgeURL)
	if !bc.IsUp() {
		log.Printf("[watcher:%s] bridge not available — S/R levels skipped", w.pos.Ticker)
		return
	}
	data, err := bc.SR(w.pos.Ticker, "1D", 200)
	if err != nil {
		log.Printf("[watcher:%s] S/R load error: %v", w.pos.Ticker, err)
		return
	}
	raw, ok := data["key_levels"]
	if !ok {
		return
	}
	levels, ok := raw.([]interface{})
	if !ok {
		return
	}
	var srLevels []float64
	for _, l := range levels {
		if v, ok := l.(float64); ok {
			srLevels = append(srLevels, v)
		}
	}
	w.srLevels = srLevels
	log.Printf("[watcher:%s] loaded %d S/R levels: %v", w.pos.Ticker, len(srLevels), srLevels)
}

// seedFromHistory loads historical daily bars from DuckDB and feeds them
// through all metrics so indicators are accurate from the first live bar.
func (w *Watcher) seedFromHistory() {
	bars, err := w.barStore.LoadBars(w.pos.Ticker, "1d", 300)
	if err != nil {
		log.Printf("[watcher:%s] could not seed from DuckDB: %v", w.pos.Ticker, err)
		return
	}
	if len(bars) == 0 {
		log.Printf("[watcher:%s] no historical bars in DuckDB for seeding", w.pos.Ticker)
		return
	}

	for _, b := range bars {
		w.vwap.Update(b.High, b.Low, b.Close, b.Volume)
		w.rsi.Update(b.Close)
		w.ema9.Update(b.Close)
		w.ema21.Update(b.Close)
		w.macd.Update(b.Close)
		w.atr.Update(b.High, b.Low, b.Close)
		w.volTracker.Update(b.Volume)
		w.barBuf.Add(Bar{High: b.High, Low: b.Low, Close: b.Close, Volume: b.Volume})
		w.price = b.Close
	}

	log.Printf("[watcher:%s] seeded with %d historical bars from DuckDB", w.pos.Ticker, len(bars))
}

// checkSRProximity fires an alert if price is within 0.3% of a key S/R level.
func (w *Watcher) checkSRProximity(price float64) {
	const proximityPct = 0.003 // 0.3%
	for _, level := range w.srLevels {
		dist := math.Abs(price-level) / level
		if dist <= proximityPct {
			side := "resistance"
			if level < price {
				side = "support"
			}
			alertType := alerts.AlertType(fmt.Sprintf("sr_proximity_%.0f", level))
			if !w.cooldown.CanAlert(w.pos.Ticker, alertType, 30*time.Minute) {
				continue
			}
			w.cooldown.Record(w.pos.Ticker, alertType)
			w.events <- Event{
				Type:    EventAlert,
				Ticker:  w.pos.Ticker,
				Price:   price,
				Message: fmt.Sprintf("📍 %s approaching %s $%.2f (%.2f%% away)", w.pos.Ticker, side, level, dist*100),
				Time:    time.Now(),
			}
		}
	}
}
