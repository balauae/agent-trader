// Package tvconn manages TradingView WebSocket connections.
package tvconn

import "time"

// Quote holds real-time quote data from a qsd message.
type Quote struct {
	Ticker    string  `json:"ticker"`
	Price     float64 `json:"price"`
	Change    float64 `json:"change"`
	ChangePct float64 `json:"change_pct"`
	Volume    float64 `json:"volume"`
	Bid       float64 `json:"bid"`
	Ask       float64 `json:"ask"`
	Time      time.Time
}

// Bar holds OHLCV bar data from a du message.
type Bar struct {
	Time   time.Time `json:"time"`
	Open   float64   `json:"open"`
	High   float64   `json:"high"`
	Low    float64   `json:"low"`
	Close  float64   `json:"close"`
	Volume float64   `json:"volume"`
}

// SeriesUpdate holds bar updates from a du message — may contain multiple bars.
type SeriesUpdate struct {
	Bars []Bar
}

// Message represents a parsed TV WebSocket message.
type Message struct {
	Method string
	// Only one of these is populated per message.
	Quote        *Quote
	SeriesUpdate *SeriesUpdate
	RawArgs      []interface{}
}

// ExchangeMap maps ticker symbols to their exchange prefix.
// Start with a hardcoded map, later use TV's symbol search.
var ExchangeMap = map[string]string{
	// NASDAQ
	"MU":   "NASDAQ",
	"MRVL": "NASDAQ",
	"AAPL": "NASDAQ",
	"MSFT": "NASDAQ",
	"GOOG": "NASDAQ",
	"GOOGL": "NASDAQ",
	"AMZN": "NASDAQ",
	"META": "NASDAQ",
	"NVDA": "NASDAQ",
	"AMD":  "NASDAQ",
	"INTC": "NASDAQ",
	"TSLA": "NASDAQ",
	"NFLX": "NASDAQ",
	"AVGO": "NASDAQ",
	"QCOM": "NASDAQ",
	"COST": "NASDAQ",
	// NYSE
	"GLD":  "NYSE",
	"SPY":  "NYSE",
	"QQQ":  "NASDAQ",
	"IWM":  "NYSE",
	"DIA":  "NYSE",
	"GS":   "NYSE",
	"JPM":  "NYSE",
	"BAC":  "NYSE",
	"WMT":  "NYSE",
	"V":    "NYSE",
	"MA":   "NYSE",
	// AMEX
	"SLV":  "AMEX",
	"XLF":  "AMEX",
	"XLE":  "AMEX",
	"XLK":  "AMEX",
}

// GetExchange returns the exchange prefix for a ticker, defaulting to NASDAQ.
func GetExchange(ticker string) string {
	if ex, ok := ExchangeMap[ticker]; ok {
		return ex
	}
	return "NASDAQ"
}

// GetExchangeOrOverride uses an explicit override if provided, otherwise looks up.
func GetExchangeOrOverride(ticker, override string) string {
	if override != "" {
		return override
	}
	return GetExchange(ticker)
}
