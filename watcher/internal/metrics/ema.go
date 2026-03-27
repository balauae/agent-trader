package metrics

// EMA computes an Exponential Moving Average.
//
// The first `period` values are used to compute an SMA as the initial EMA.
// After that:
//
//	multiplier = 2 / (period + 1)
//	EMA = (value - prevEMA) * multiplier + prevEMA
type EMA struct {
	period     int
	multiplier float64
	value      float64
	count      int
	sum        float64 // used during SMA seeding
	ready      bool
}

// NewEMA creates a new EMA calculator with the given period.
func NewEMA(period int) *EMA {
	return &EMA{
		period:     period,
		multiplier: 2.0 / (float64(period) + 1.0),
	}
}

// Update adds a new value and recalculates the EMA.
func (e *EMA) Update(val float64) {
	e.count++

	if e.count <= e.period {
		// Accumulate for SMA seed
		e.sum += val
		if e.count == e.period {
			e.value = e.sum / float64(e.period)
			e.ready = true
		}
		return
	}

	// EMA calculation
	e.value = (val-e.value)*e.multiplier + e.value
}

// Value returns the current EMA value.
func (e *EMA) Value() float64 {
	return e.value
}

// Ready returns true when enough values have been processed.
func (e *EMA) Ready() bool {
	return e.ready
}

// Count returns the number of values processed.
func (e *EMA) Count() int {
	return e.count
}

// Period returns the EMA period.
func (e *EMA) Period() int {
	return e.period
}
