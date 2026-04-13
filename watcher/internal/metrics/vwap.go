// Package metrics provides technical indicator calculators.
package metrics

import "math"

// VWAP computes a running Volume-Weighted Average Price.
// VWAP = cumulative(typical_price * volume) / cumulative(volume)
type VWAP struct {
	cumTPV   float64 // cumulative (typical_price * volume)
	cumVol   float64 // cumulative volume
	cumTPSqV float64 // cumulative (typical_price^2 * volume) for variance
	value    float64
	count    int
}

// NewVWAP creates a new VWAP calculator.
func NewVWAP() *VWAP {
	return &VWAP{}
}

// Update adds a new bar to the VWAP calculation.
func (v *VWAP) Update(high, low, close, volume float64) {
	typicalPrice := (high + low + close) / 3.0
	v.cumTPV += typicalPrice * volume
	v.cumTPSqV += typicalPrice * typicalPrice * volume
	v.cumVol += volume
	v.count++
	if v.cumVol > 0 {
		v.value = v.cumTPV / v.cumVol
	}
}

// UpdateFromTypical updates using a pre-computed typical price.
func (v *VWAP) UpdateFromTypical(typicalPrice, volume float64) {
	v.cumTPV += typicalPrice * volume
	v.cumTPSqV += typicalPrice * typicalPrice * volume
	v.cumVol += volume
	v.count++
	if v.cumVol > 0 {
		v.value = v.cumTPV / v.cumVol
	}
}

// Value returns the current VWAP value.
func (v *VWAP) Value() float64 {
	return v.value
}

// Count returns how many bars have been processed.
func (v *VWAP) Count() int {
	return v.count
}

// CumTPV returns the cumulative typical-price * volume (for state persistence).
func (v *VWAP) CumTPV() float64 {
	return v.cumTPV
}

// CumVol returns the cumulative volume (for state persistence).
func (v *VWAP) CumVol() float64 {
	return v.cumVol
}

// Reset clears the VWAP state (e.g., at start of new trading day).
func (v *VWAP) Reset() {
	v.cumTPV = 0
	v.cumTPSqV = 0
	v.cumVol = 0
	v.value = 0
	v.count = 0
}

// Ready returns true when at least one bar has been processed.
func (v *VWAP) Ready() bool {
	return v.count > 0
}

// StdDev returns the standard deviation of typical prices around VWAP,
// computed from the running variance: sqrt(cumTPSqV/cumVol - vwap^2).
func (v *VWAP) StdDev() float64 {
	if v.cumVol <= 0 {
		return 0
	}
	variance := v.cumTPSqV/v.cumVol - v.value*v.value
	if variance < 0 {
		variance = 0 // guard against floating-point noise
	}
	return math.Sqrt(variance)
}

// Upper1Sigma returns VWAP + 1 standard deviation.
func (v *VWAP) Upper1Sigma() float64 { return v.value + v.StdDev() }

// Upper2Sigma returns VWAP + 2 standard deviations.
func (v *VWAP) Upper2Sigma() float64 { return v.value + 2*v.StdDev() }

// Lower1Sigma returns VWAP - 1 standard deviation.
func (v *VWAP) Lower1Sigma() float64 { return v.value - v.StdDev() }

// Lower2Sigma returns VWAP - 2 standard deviations.
func (v *VWAP) Lower2Sigma() float64 { return v.value - 2*v.StdDev() }
