package alerts

import (
	"sync"
	"time"
)

// RateLimiter limits global alert rate using a token bucket.
// Default: 5 alerts per minute across all tickers.
type RateLimiter struct {
	mu       sync.Mutex
	tokens   float64
	maxTokens float64
	refillRate float64 // tokens per second
	lastRefill time.Time
}

// NewRateLimiter creates a limiter allowing maxPerMin alerts per minute.
func NewRateLimiter(maxPerMin int) *RateLimiter {
	return &RateLimiter{
		tokens:     float64(maxPerMin),
		maxTokens:  float64(maxPerMin),
		refillRate: float64(maxPerMin) / 60.0,
		lastRefill: time.Now(),
	}
}

// Allow returns true if an alert can be sent (consumes one token).
// Critical alerts always pass regardless of rate limit.
func (r *RateLimiter) Allow(severity Severity) bool {
	if severity == SeverityCritical {
		return true
	}
	r.mu.Lock()
	defer r.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(r.lastRefill).Seconds()
	r.tokens += elapsed * r.refillRate
	if r.tokens > r.maxTokens {
		r.tokens = r.maxTokens
	}
	r.lastRefill = now

	if r.tokens >= 1 {
		r.tokens--
		return true
	}
	return false
}
