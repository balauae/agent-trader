package alerts

import (
	"fmt"
	"time"

	"github.com/bala/tradedesk-watcher/internal/position"
)

// CheckStopHit returns an alert if the stop has been hit.
func CheckStopHit(ticker string, price float64, pos *position.Position) *Alert {
	if pos == nil || pos.Stop == 0 {
		return nil
	}
	hit := false
	if pos.GetDirection() == position.Long && price <= pos.Stop {
		hit = true
	} else if pos.GetDirection() == position.Short && price >= pos.Stop {
		hit = true
	}
	if !hit {
		return nil
	}
	return &Alert{
		Type:     AlertStopHit,
		Severity: SeverityCritical,
		Ticker:   ticker,
		Price:    price,
		Message:  fmt.Sprintf("🚨 %s STOP HIT $%.2f | Stop was $%.2f", ticker, price, pos.Stop),
		Time:     time.Now(),
	}
}

// CheckTargetHit returns an alert if the target has been hit.
func CheckTargetHit(ticker string, price float64, pos *position.Position) *Alert {
	if pos == nil || pos.Target == 0 {
		return nil
	}
	hit := false
	if pos.GetDirection() == position.Long && price >= pos.Target {
		hit = true
	} else if pos.GetDirection() == position.Short && price <= pos.Target {
		hit = true
	}
	if !hit {
		return nil
	}
	return &Alert{
		Type:     AlertTargetHit,
		Severity: SeverityCritical,
		Ticker:   ticker,
		Price:    price,
		Message:  fmt.Sprintf("🎯 %s TARGET HIT $%.2f | Target $%.2f", ticker, price, pos.Target),
		Time:     time.Now(),
	}
}

// CheckNearStop returns a warning if price is within thresholdPct of the stop.
func CheckNearStop(ticker string, price float64, pos *position.Position, thresholdPct float64) *Alert {
	if pos == nil || pos.Stop == 0 {
		return nil
	}
	dist := pos.StopDistancePct(price)
	if dist < 0 || dist > thresholdPct {
		return nil
	}
	return &Alert{
		Type:     AlertNearStop,
		Severity: SeverityWarning,
		Ticker:   ticker,
		Price:    price,
		Message:  fmt.Sprintf("⚠️ %s approaching stop — $%.2f (stop $%.2f, %.1f%% away)", ticker, price, pos.Stop, dist),
		Time:     time.Now(),
	}
}

// CheckVWAPBreak returns a warning if price crossed below VWAP.
func CheckVWAPBreak(ticker string, price, prevPrice, vwap float64) *Alert {
	if vwap == 0 {
		return nil
	}
	if prevPrice > vwap && price <= vwap {
		return &Alert{
			Type:     AlertVWAPBreak,
			Severity: SeverityWarning,
			Ticker:   ticker,
			Price:    price,
			VWAP:     vwap,
			Message:  fmt.Sprintf("📉 %s broke below VWAP $%.2f — weakening", ticker, vwap),
			Time:     time.Now(),
		}
	}
	return nil
}

// CheckVWAPReclaim returns an info alert if price crossed above VWAP.
func CheckVWAPReclaim(ticker string, price, prevPrice, vwap float64) *Alert {
	if vwap == 0 {
		return nil
	}
	if prevPrice <= vwap && price > vwap {
		return &Alert{
			Type:     AlertVWAPReclaim,
			Severity: SeverityInfo,
			Ticker:   ticker,
			Price:    price,
			VWAP:     vwap,
			Message:  fmt.Sprintf("📈 %s reclaimed VWAP $%.2f — strengthening", ticker, vwap),
			Time:     time.Now(),
		}
	}
	return nil
}

// CheckHighVolume returns a warning if volume is spiking on a red candle.
func CheckHighVolume(ticker string, price, open, volume, avgVolume float64, multiplier float64) *Alert {
	if avgVolume == 0 || volume < avgVolume*multiplier {
		return nil
	}
	isRed := price < open
	if !isRed {
		return nil
	}
	ratio := volume / avgVolume
	return &Alert{
		Type:     AlertHighVolume,
		Severity: SeverityWarning,
		Ticker:   ticker,
		Price:    price,
		Message:  fmt.Sprintf("📊 %s unusual volume on sell candle — %.1fx avg", ticker, ratio),
		Time:     time.Now(),
	}
}

// CheckFlashMove returns a critical alert if price moved >thresholdPct in one bar.
func CheckFlashMove(ticker string, price, prevClose float64, thresholdPct float64) *Alert {
	if prevClose == 0 {
		return nil
	}
	changePct := ((price - prevClose) / prevClose) * 100
	if changePct > -thresholdPct && changePct < thresholdPct {
		return nil
	}
	dir := "⚡ up"
	if changePct < 0 {
		dir = "⚡ down"
	}
	return &Alert{
		Type:     AlertFlashMove,
		Severity: SeverityCritical,
		Ticker:   ticker,
		Price:    price,
		Message:  fmt.Sprintf("%s %s flash move %.1f%% in 1 bar — check catalyst", ticker, dir, changePct),
		Time:     time.Now(),
	}
}
