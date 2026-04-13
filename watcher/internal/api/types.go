package api

// WatchRequest starts a new watcher.
type WatchRequest struct {
	Ticker   string  `json:"ticker"`
	Exchange string  `json:"exchange,omitempty"`
	Shares   float64 `json:"shares,omitempty"`
	AvgPrice float64 `json:"avg_price,omitempty"`
	Stop     float64 `json:"stop,omitempty"`
	Target   float64 `json:"target,omitempty"`
	Direction string `json:"direction,omitempty"`
}

// UpdateRequest updates stop/target levels.
type UpdateRequest struct {
	Stop   float64 `json:"stop,omitempty"`
	Target float64 `json:"target,omitempty"`
}

// PauseRequest pauses alerts for N minutes.
type PauseRequest struct {
	Minutes int `json:"minutes"`
}

// StatusResponse is the full status of one watcher.
type StatusResponse struct {
	Ticker         string  `json:"ticker"`
	State          string  `json:"state"`
	Price          float64 `json:"price"`
	VWAP           float64 `json:"vwap"`
	RSI            float64 `json:"rsi"`
	AvgPrice       float64 `json:"avg_price"`
	PnLDollars     float64 `json:"pnl_dollars"`
	PnLPercent     float64 `json:"pnl_pct"`
	Stop           float64 `json:"stop"`
	Target         float64 `json:"target"`
	VWAPDistPct    float64 `json:"vwap_dist_pct"`
	StopDistPct    float64 `json:"stop_dist_pct"`
	TargetDistPct  float64 `json:"target_dist_pct"`
	StartedAt      string  `json:"started_at"`
	Restarts       int     `json:"restarts"`
}

// HealthResponse is the overall system health.
type HealthResponse struct {
	Status       string           `json:"status"`
	Uptime       string           `json:"uptime"`
	WatcherCount int              `json:"watcher_count"`
	Silenced     bool             `json:"silenced"`
	Watchers     []StatusResponse `json:"watchers"`
}

// ErrorResponse wraps an error message.
type ErrorResponse struct {
	Error string `json:"error"`
}

// OKResponse wraps a success message.
type OKResponse struct {
	OK      bool   `json:"ok"`
	Message string `json:"message"`
}

// AnalyzeResponse matches the Python bridge /analyze/{ticker} format.
type AnalyzeResponse struct {
	Ticker          string              `json:"ticker"`
	Timeframe       string              `json:"timeframe"`
	Price           float64             `json:"price"`
	Bias            string              `json:"bias"`
	ConfluenceScore string              `json:"confluence_score"`
	Indicators      AnalyzeIndicators   `json:"indicators"`
	Levels          AnalyzeLevels       `json:"levels"`
	Signals         []string            `json:"signals"`
	VWAP            AnalyzeVWAP         `json:"vwap"`
}

// AnalyzeIndicators holds all computed indicator values.
type AnalyzeIndicators struct {
	Close        float64  `json:"close"`
	EMA9         float64  `json:"ema_9"`
	EMA21        float64  `json:"ema_21"`
	SMA50        *float64 `json:"sma_50"`
	SMA200       *float64 `json:"sma_200"`
	MACDLine     float64  `json:"macd_line"`
	MACDSignal   float64  `json:"macd_signal"`
	MACDHist     float64  `json:"macd_histogram"`
	RSI          float64  `json:"rsi"`
	BBUpper      float64  `json:"bb_upper"`
	BBMid        float64  `json:"bb_mid"`
	BBLower      float64  `json:"bb_lower"`
	ATR          float64  `json:"atr"`
	VWAP         float64  `json:"vwap"`
	Volume       float64  `json:"volume"`
	VolumeSMA20  float64  `json:"volume_sma_20"`
	VolAboveAvg  bool     `json:"volume_above_avg"`
}

// AnalyzeLevels holds key price levels.
type AnalyzeLevels struct {
	Support    float64 `json:"support"`
	Resistance float64 `json:"resistance"`
	EMA9       float64 `json:"ema_9"`
	EMA21      float64 `json:"ema_21"`
	BBUpper    float64 `json:"bb_upper"`
	BBLower    float64 `json:"bb_lower"`
}

// AnalyzeVWAP holds VWAP and band data.
type AnalyzeVWAP struct {
	Value       float64 `json:"value"`
	Upper1S     float64 `json:"upper_1s"`
	Upper2S     float64 `json:"upper_2s"`
	Lower1S     float64 `json:"lower_1s"`
	Lower2S     float64 `json:"lower_2s"`
	PriceVsVWAP string  `json:"price_vs_vwap"`
	DistancePct float64 `json:"distance_pct"`
}
