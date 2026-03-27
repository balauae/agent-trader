package metrics

import "math"

// ATR computes the Average True Range using Wilder's smoothing.
//
// True Range = max(high-low, |high-prevClose|, |low-prevClose|)
// First `period` TRs use simple average to seed.
// After that: ATR = prevATR * (period-1)/period + TR * 1/period
type ATR struct {
	period    int
	prevClose float64
	value     float64
	count     int
	sum       float64 // used during seeding phase
	ready     bool
}

// NewATR creates a new ATR calculator with the given period (typically 14).
func NewATR(period int) *ATR {
	return &ATR{period: period}
}

// Update adds a new bar's high, low, close and recalculates ATR.
func (a *ATR) Update(high, low, close float64) {
	a.count++

	if a.count == 1 {
		// First bar: TR = high - low (no previous close)
		tr := high - low
		a.sum += tr
		a.prevClose = close
		return
	}

	// True Range
	tr := math.Max(high-low, math.Max(
		math.Abs(high-a.prevClose),
		math.Abs(low-a.prevClose),
	))
	a.prevClose = close

	if a.count <= a.period {
		// Seeding phase: accumulate for simple average
		a.sum += tr
		if a.count == a.period {
			a.value = a.sum / float64(a.period)
			a.ready = true
		}
		return
	}

	// Wilder's smoothing
	p := float64(a.period)
	a.value = (a.value*(p-1) + tr) / p
}

// Value returns the current ATR value.
func (a *ATR) Value() float64 {
	return a.value
}

// Ready returns true when enough bars have been processed.
func (a *ATR) Ready() bool {
	return a.ready
}

// Count returns the number of bars processed.
func (a *ATR) Count() int {
	return a.count
}
