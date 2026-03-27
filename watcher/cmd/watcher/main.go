// Command watcher is the TradeDesk Watcher entrypoint.
// It connects to TradingView's real-time WebSocket feed, subscribes to a
// ticker, computes running VWAP/RSI on each bar update, and optionally
// evaluates stop-loss / take-profit levels.
package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"time"

	"github.com/bala/tradedesk-watcher/internal/config"
	"github.com/bala/tradedesk-watcher/internal/market"
	"github.com/bala/tradedesk-watcher/internal/metrics"
	"github.com/bala/tradedesk-watcher/internal/position"
	"github.com/bala/tradedesk-watcher/internal/tvconn"
)

func main() {
	// ── flags ───────────────────────────────────────────────────────────
	ticker := flag.String("ticker", "MU", "ticker symbol to watch")
	exchange := flag.String("exchange", "", "exchange override (default: auto-detect)")
	timeout := flag.Duration("timeout", 60*time.Second, "run duration (0 = forever)")
	stop := flag.Float64("stop", 0, "stop-loss price (0 = disabled)")
	target := flag.Float64("target", 0, "take-profit price (0 = disabled)")
	cfgPath := flag.String("config", "config.json", "path to config file")
	posPath := flag.String("positions", "", "path to positions file (overrides config)")
	flag.Parse()

	*ticker = strings.ToUpper(*ticker)

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
