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
	Status        string           `json:"status"`
	Uptime        string           `json:"uptime"`
	WatcherCount  int              `json:"watcher_count"`
	Watchers      []StatusResponse `json:"watchers"`
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
