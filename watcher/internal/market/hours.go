// Package market provides Abu Dhabi (UTC+4) market-hours session detection.
//
// US market hours mapped to Abu Dhabi time (Asia/Dubai, UTC+4):
//
//	12:00 PM – 5:30 PM   Pre-market  (poll 60s, critical alerts only)
//	 5:30 PM – Midnight   Market open (poll 30s, all alerts)
//	Midnight  – 4:00 AM   After-hours (poll 60s, critical alerts only)
//	 4:00 AM – 12:00 PM   Overnight   (paused)
package market

import (
	"time"
)

// Session represents a US market session as seen from Abu Dhabi.
type Session int

const (
	Overnight  Session = iota // 04:00 – 12:00 Abu Dhabi — paused
	PreMarket                 // 12:00 – 17:30 Abu Dhabi
	MarketOpen                // 17:30 – 00:00 Abu Dhabi
	AfterHours                // 00:00 – 04:00 Abu Dhabi
)

// String returns a human-readable session name.
func (s Session) String() string {
	switch s {
	case PreMarket:
		return "Pre-Market"
	case MarketOpen:
		return "Market"
	case AfterHours:
		return "After-Hours"
	default:
		return "Overnight"
	}
}

// IsActive returns true if the session should be polling for data.
func (s Session) IsActive() bool {
	return s != Overnight
}

// dubaiLoc caches the Abu Dhabi timezone.
var dubaiLoc *time.Location

func init() {
	var err error
	dubaiLoc, err = time.LoadLocation("Asia/Dubai")
	if err != nil {
		// Fallback to fixed offset UTC+4
		dubaiLoc = time.FixedZone("Gulf", 4*60*60)
	}
}

// CurrentSession returns the current market session based on Abu Dhabi time.
func CurrentSession() Session {
	return SessionAt(time.Now())
}

// SessionAt returns the market session for a given time.
func SessionAt(t time.Time) Session {
	dubai := t.In(dubaiLoc)
	hour := dubai.Hour()
	minute := dubai.Minute()
	totalMins := hour*60 + minute

	switch {
	case totalMins >= 4*60 && totalMins < 12*60:
		// 04:00 – 12:00 → Overnight
		return Overnight
	case totalMins >= 12*60 && totalMins < 17*60+30:
		// 12:00 – 17:30 → Pre-Market
		return PreMarket
	case totalMins >= 17*60+30:
		// 17:30 – 23:59 → Market Open
		return MarketOpen
	default:
		// 00:00 – 04:00 → After-Hours
		return AfterHours
	}
}

// PollInterval returns the recommended poll interval for the given session.
func PollInterval(s Session) time.Duration {
	switch s {
	case MarketOpen:
		return 30 * time.Second
	case PreMarket, AfterHours:
		return 60 * time.Second
	default:
		return 0 // paused
	}
}

// DubaiLocation returns the Asia/Dubai timezone location.
func DubaiLocation() *time.Location {
	return dubaiLoc
}
