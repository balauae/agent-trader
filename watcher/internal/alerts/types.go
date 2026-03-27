package alerts

import "time"

// Severity of an alert.
type Severity int

const (
	SeverityCritical Severity = iota // stop hit, target hit, flash crash
	SeverityWarning                  // near stop, VWAP break, high volume
	SeverityInfo                     // periodic update, setup detected
)

func (s Severity) String() string {
	switch s {
	case SeverityCritical:
		return "critical"
	case SeverityWarning:
		return "warning"
	default:
		return "info"
	}
}

// AlertType identifies what triggered the alert.
type AlertType string

const (
	AlertStopHit       AlertType = "stop_hit"
	AlertTargetHit     AlertType = "target_hit"
	AlertNearStop      AlertType = "near_stop"
	AlertVWAPBreak     AlertType = "vwap_break"
	AlertVWAPReclaim   AlertType = "vwap_reclaim"
	AlertHighVolume    AlertType = "high_volume"
	AlertFlashMove     AlertType = "flash_move"
	AlertConsecRed     AlertType = "consec_red"
	AlertPnLThreshold  AlertType = "pnl_threshold"
	AlertPeriodicUpdate AlertType = "periodic_update"
)

// Alert represents a triggered alert event.
type Alert struct {
	Type     AlertType
	Severity Severity
	Ticker   string
	Price    float64
	VWAP     float64
	RSI      float64
	PnL      float64
	Message  string
	Time     time.Time
}
