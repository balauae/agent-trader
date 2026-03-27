package alerts

import (
	"fmt"
	"time"
)

// FormatSnapshot formats a multi-position P&L snapshot for Telegram.
func FormatSnapshot(positions []PositionStatus, ts time.Time) string {
	abu := ts.In(time.FixedZone("Abu Dhabi", 4*3600))
	header := fmt.Sprintf("🔔 TradeDesk Update — %s\n\n", abu.Format("3:04 PM"))
	body := ""
	totalPnL := 0.0
	for _, p := range positions {
		emoji := "🟢"
		if p.PnL < 0 {
			emoji = "🔴"
		}
		sign := "+"
		if p.PnL < 0 {
			sign = ""
		}
		body += fmt.Sprintf("%s %-5s $%-8.2f | P&L %s$%.0f\n", emoji, p.Ticker, p.Price, sign, p.PnL)
		totalPnL += p.PnL
	}
	sign := "+"
	if totalPnL < 0 {
		sign = ""
	}
	body += fmt.Sprintf("─────────────────────────\n💰 Total: %s$%.0f", sign, totalPnL)
	return header + body
}

// PositionStatus holds live position data for snapshot formatting.
type PositionStatus struct {
	Ticker string
	Price  float64
	VWAP   float64
	PnL    float64
}
