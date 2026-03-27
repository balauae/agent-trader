// Command watcher is the TradeDesk Watcher entrypoint.
// It connects to TradingView's real-time WebSocket feed, subscribes to a
// ticker, computes running VWAP/RSI on each bar update, and optionally
// evaluates stop-loss / take-profit levels.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"time"

	"github.com/bala/tradedesk-watcher/internal/api"
	"github.com/bala/tradedesk-watcher/internal/config"
	"github.com/bala/tradedesk-watcher/internal/engine"
	"github.com/bala/tradedesk-watcher/internal/market"
	"github.com/bala/tradedesk-watcher/internal/metrics"
	"github.com/bala/tradedesk-watcher/internal/notifier"
	"github.com/bala/tradedesk-watcher/internal/position"
	"github.com/bala/tradedesk-watcher/internal/tvconn"
)

func main() {
	// ── flags ───────────────────────────────────────────────────────────
	ticker := flag.String("ticker", "", "ticker symbol to watch (single mode)")
	exchange := flag.String("exchange", "", "exchange override (default: auto-detect)")
	timeout := flag.Duration("timeout", 60*time.Second, "run duration (0 = forever)")
	stop := flag.Float64("stop", 0, "stop-loss price (0 = disabled)")
	target := flag.Float64("target", 0, "take-profit price (0 = disabled)")
	cfgPath := flag.String("config", "config.json", "path to config file")
	posPath := flag.String("positions", "", "path to positions file (overrides config)")
	multi := flag.Bool("multi", false, "watch all positions from positions.json simultaneously")
	flag.Parse()

	if *ticker != "" {
		*ticker = strings.ToUpper(*ticker)
	}

	// ── config ──────────────────────────────────────────────────────────
	cfg, err := config.Load(*cfgPath)
	if err != nil {
		log.Fatalf("config: %v", err)
	}

	// ── auth ────────────────────────────────────────────────────────────
	authToken, err := config.LoadAuthToken(cfg.SecretsDir)
	if err != nil {
		log.Fatalf("auth: %v", err)
	}

	// ── position (optional) ─────────────────────────────────────────────
	posFile := cfg.PositionsFile
	if *posPath != "" {
		posFile = *posPath
	}
	positions, _ := position.LoadPositions(posFile) // ok if missing
	pos := position.FindByTicker(positions, *ticker)

	// CLI flags override position stop/target
	if *stop != 0 {
		if pos == nil {
			pos = &position.Position{Ticker: *ticker}
		}
		pos.Stop = *stop
	}
	if *target != 0 {
		if pos == nil {
			pos = &position.Position{Ticker: *ticker}
		}
		pos.Target = *target
	}

	// ── multi-ticker mode ───────────────────────────────────────────────
	if *multi || *ticker == "" {
		runMulti(cfg, *posPath, *timeout)
		return
	}

	// ── market session ──────────────────────────────────────────────────
	sess := market.CurrentSession()
	fmt.Printf("Session  : %s\n", sess)

	// ── metrics init ────────────────────────────────────────────────────
	vwap := metrics.NewVWAP()
	rsi := metrics.NewRSI(cfg.RSIPeriod)
	atr := metrics.NewATR(cfg.ATRPeriod)
	ema9 := metrics.NewEMA(cfg.EMAShort)
	ema20 := metrics.NewEMA(cfg.EMALong)
	macd := metrics.NewMACD(cfg.MACDFast, cfg.MACDSlow, cfg.MACDSignal)
	vol := metrics.NewVolumeTracker(cfg.VolumeWindow)

	// ── connect ─────────────────────────────────────────────────────────
	fmt.Printf("Connecting to TradingView WebSocket...\n")
	fmt.Printf("Ticker   : %s\n", *ticker)

	conn, err := tvconn.Connect(authToken)
	if err != nil {
		log.Fatalf("connect: %v", err)
	}
	defer conn.Close()
	fmt.Println("Connected.")

	exch := tvconn.GetExchangeOrOverride(*ticker, *exchange)
	if err := conn.Subscribe(*ticker, exch, cfg.NumBars); err != nil {
		log.Fatalf("subscribe: %v", err)
	}
	fmt.Printf("Subscribed to %s:%s (%d bars)\n\n", exch, *ticker, cfg.NumBars)

	// ── read loop in background ─────────────────────────────────────────
	go conn.ReadLoop()

	// ── timers & signals ────────────────────────────────────────────────
	var deadline <-chan time.Time
	if *timeout > 0 {
		deadline = time.After(*timeout)
		fmt.Printf("Timeout  : %s\n\n", *timeout)
	} else {
		fmt.Printf("Timeout  : none (run forever)\n\n")
	}

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt)

	var lastPrice float64

	// ── event loop ──────────────────────────────────────────────────────
	for {
		select {
		// ── quote tick ──────────────────────────────────────────────
		case q := <-conn.Quotes():
			if q == nil {
				continue
			}
			lastPrice = q.Price
			fmt.Printf("QUOTE  %s $%.2f  chg %.2f (%.2f%%)\n",
				*ticker, q.Price, q.Change, q.ChangePct)

		// ── bar update ──────────────────────────────────────────────
		case su := <-conn.Bars():
			if su == nil {
				continue
			}
			for _, bar := range su.Bars {
				// feed every indicator
				vwap.Update(bar.High, bar.Low, bar.Close, bar.Volume)
				rsi.Update(bar.Close)
				atr.Update(bar.High, bar.Low, bar.Close)
				ema9.Update(bar.Close)
				ema20.Update(bar.Close)
				macd.Update(bar.Close)
				vol.Update(bar.Volume)

				lastPrice = bar.Close

				// primary line: price | VWAP | RSI
				line := fmt.Sprintf("%s $%.2f", *ticker, bar.Close)
				if vwap.Ready() {
					line += fmt.Sprintf(" | VWAP $%.2f", vwap.Value())
				}
				if rsi.Ready() {
					line += fmt.Sprintf(" | RSI %.1f", rsi.Value())
				}
				fmt.Println(line)

				// secondary: ATR / EMA / MACD / volume
				var extras []string
				if atr.Ready() {
					extras = append(extras, fmt.Sprintf("ATR %.2f", atr.Value()))
				}
				if ema9.Ready() {
					extras = append(extras, fmt.Sprintf("EMA9 %.2f", ema9.Value()))
				}
				if ema20.Ready() {
					extras = append(extras, fmt.Sprintf("EMA20 %.2f", ema20.Value()))
				}
				if macd.Ready() {
					extras = append(extras, fmt.Sprintf("MACD %.3f / Sig %.3f / Hist %.3f",
						macd.MACDLine(), macd.Signal(), macd.Histogram()))
				}
				if vol.Ready() && vol.IsSpike(cfg.VolumeSpikeMulti) {
					extras = append(extras, fmt.Sprintf("VOL SPIKE x%.1f", vol.SpikeRatio()))
				}
				if len(extras) > 0 {
					fmt.Printf("         %s\n", strings.Join(extras, " | "))
				}

				// ── stop / target evaluation ────────────────────────
				evaluateStopTarget(*ticker, bar.Close, pos)
			}

		// ── error ───────────────────────────────────────────────────
		case err := <-conn.Errors():
			log.Printf("ws error: %v", err)

		// ── connection closed ───────────────────────────────────────
		case <-conn.Done():
			fmt.Println("Connection closed.")
			return

		// ── timeout ─────────────────────────────────────────────────
		case <-deadline:
			fmt.Printf("\nTimeout reached (%s). Shutting down.\n", *timeout)
			return

		// ── ctrl-c ──────────────────────────────────────────────────
		case <-sigCh:
			fmt.Println("\nInterrupt received. Shutting down.")
			return
		}
	}

	// silence unused import warnings during early development
	_ = sess
	_ = lastPrice
}

// evaluateStopTarget prints a warning when price breaches stop or target.
func evaluateStopTarget(ticker string, price float64, pos *position.Position) {
	if pos == nil {
		return
	}
	dir := pos.GetDirection()

	if pos.Stop > 0 {
		dist := pos.StopDistancePct(price)
		switch dir {
		case position.Long:
			if price <= pos.Stop {
				fmt.Printf("*** STOP HIT *** %s $%.2f <= stop $%.2f\n", ticker, price, pos.Stop)
			} else if dist < 1.0 {
				fmt.Printf("  ~ stop warning ~ %s %.1f%% from stop $%.2f\n", ticker, dist, pos.Stop)
			}
		case position.Short:
			if price >= pos.Stop {
				fmt.Printf("*** STOP HIT *** %s $%.2f >= stop $%.2f\n", ticker, price, pos.Stop)
			} else if dist < 1.0 {
				fmt.Printf("  ~ stop warning ~ %s %.1f%% from stop $%.2f\n", ticker, dist, pos.Stop)
			}
		}
	}

	if pos.Target > 0 {
		dist := pos.TargetDistancePct(price)
		switch dir {
		case position.Long:
			if price >= pos.Target {
				fmt.Printf("*** TARGET HIT *** %s $%.2f >= target $%.2f\n", ticker, price, pos.Target)
			} else if dist < 1.0 {
				fmt.Printf("  ~ target close ~ %s %.1f%% from target $%.2f\n", ticker, dist, pos.Target)
			}
		case position.Short:
			if price <= pos.Target {
				fmt.Printf("*** TARGET HIT *** %s $%.2f <= target $%.2f\n", ticker, price, pos.Target)
			} else if dist < 1.0 {
				fmt.Printf("  ~ target close ~ %s %.1f%% from target $%.2f\n", ticker, dist, pos.Target)
			}
		}
	}
}

// runMulti watches all positions from positions.json simultaneously using the supervisor.
func runMulti(cfg *config.Settings, posPath string, timeout time.Duration) {
	posFile := cfg.PositionsFile
	if posPath != "" {
		posFile = posPath
	}

	positions, err := position.LoadPositions(posFile)
	if err != nil {
		log.Fatalf("positions: %v", err)
	}
	if len(positions) == 0 {
		log.Fatal("no positions found in", posFile)
	}

	fmt.Printf("🔭 Multi-ticker mode — watching %d positions\n\n", len(positions))

	// Init Telegram notifier
	ntf, err := notifier.New(cfg.SecretsDir)
	if err != nil {
		log.Printf("⚠️ Telegram notifier unavailable: %v — alerts to stdout only", err)
		ntf = nil
	} else {
		fmt.Println("📲 Telegram notifier ready")
		ntf.Send(fmt.Sprintf("👁️ TradeDesk Watcher started — watching %d positions", len(positions)))
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	registryPath := cfg.DataDir + "/registry.json"
	sup := engine.NewSupervisor(cfg, registryPath)
	sup.LoadSilenceState()
	sup.Start(positions)

	// Start HTTP API server
	apiServer := api.New(cfg.SocketPath, sup)
	if err := apiServer.Start(); err != nil {
		log.Printf("⚠️ API server unavailable: %v", err)
	} else {
		fmt.Printf("🔌 API socket: %s\n", cfg.SocketPath)
	}

	var deadline <-chan time.Time
	if timeout > 0 {
		deadline = time.After(timeout)
		fmt.Printf("Timeout: %s\n\n", timeout)
	}

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt)

	for {
		select {
		case evt := <-sup.Events():
			switch evt.Type {
			case engine.EventPriceUpdate:
				fmt.Println(evt.Message)
			case engine.EventAlert:
				fmt.Printf("🚨 ALERT: %s\n", evt.Message)
				if ntf != nil && !sup.IsSilenced() {
					ntf.Send(evt.Message)
				} else if sup.IsSilenced() {
					fmt.Printf("   (silenced)\n")
				}
			case engine.EventStateChange:
				fmt.Printf("[%s] %s\n", evt.Ticker, evt.Message)
			case engine.EventPanic:
				msg := fmt.Sprintf("💥 PANIC [%s]: %v", evt.Ticker, evt.Error)
				fmt.Println(msg)
				if ntf != nil {
					ntf.Send(msg)
				}
			}
		case <-deadline:
			fmt.Printf("\nTimeout reached (%s). Shutting down.\n", timeout)
			if ntf != nil {
				ntf.SendNow("👋 TradeDesk Watcher stopped")
				ntf.Close()
			}
			sup.Stop()
			return
		case <-sigCh:
			fmt.Println("\nInterrupt. Shutting down.")
			if ntf != nil {
				ntf.SendNow("👋 TradeDesk Watcher stopped")
				ntf.Close()
			}
			sup.Stop()
			return
		case <-ctx.Done():
			return
		}
	}
}
