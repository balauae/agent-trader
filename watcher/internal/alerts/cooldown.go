package alerts

import (
	"sync"
	"time"
)

// CooldownTracker prevents alert spam by enforcing per-type-per-ticker cooldowns.
type CooldownTracker struct {
	mu      sync.RWMutex
	records map[string]time.Time // key: "MU_stop_warning"
}

// NewCooldownTracker creates a new tracker.
func NewCooldownTracker() *CooldownTracker {
	return &CooldownTracker{
		records: make(map[string]time.Time),
	}
}

// CanAlert returns true if enough time has passed since the last alert of this type.
func (c *CooldownTracker) CanAlert(ticker string, alertType AlertType, cooldown time.Duration) bool {
	key := string(ticker) + "_" + string(alertType)
	c.mu.RLock()
	last, ok := c.records[key]
	c.mu.RUnlock()
	if !ok {
		return true
	}
	return time.Since(last) >= cooldown
}

// Record marks an alert as fired now.
func (c *CooldownTracker) Record(ticker string, alertType AlertType) {
	key := string(ticker) + "_" + string(alertType)
	c.mu.Lock()
	c.records[key] = time.Now()
	c.mu.Unlock()
}

// Reset clears the cooldown for a specific type (e.g. after levels change).
func (c *CooldownTracker) Reset(ticker string, alertType AlertType) {
	key := string(ticker) + "_" + string(alertType)
	c.mu.Lock()
	delete(c.records, key)
	c.mu.Unlock()
}
