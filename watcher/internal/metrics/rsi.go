package metrics

// RSI computes the Relative Strength Index using Wilder's smoothing method.
//
// First `period` bars use simple average to seed avg_gain and avg_loss.
// After that:
//
//	avg_gain = prev_avg_gain * (period-1)/period + current_gain * 1/period
//	avg_loss = prev_avg_loss * (period-1)/period + current_loss * 1/period
//	RS = avg_gain / avg_loss
//	RSI = 100 - (100 / (1 + RS))
type RSI struct {
	period    int
	prevClose float64
	avgGain   float64
	avgLoss   float64
	count     int
	gains     []float64 // only used during seeding phase
	losses    []float64
	value     float64
	ready     bool
}

// NewRSI creates a new RSI calculator with the given period (typically 14).
func NewRSI(period int) *RSI {
	return &RSI{
		period: period,
		gains:  make([]float64, 0, period),
		losses: make([]float64, 0, period),
	}
}

// Update adds a new close price and recalculates RSI.
func (r *RSI) Update(close float64) {
	r.count++

	if r.count == 1 {
		r.prevClose = close
		return
	}

	change := close - r.prevClose
	r.prevClose = close

	gain := 0.0
	loss := 0.0
	if change > 0 {
		gain = change
	} else {
		loss = -change
	}

	if r.count <= r.period+1 {
		// Seeding phase: collect gains and losses
		r.gains = append(r.gains, gain)
		r.losses = append(r.losses, loss)

		if r.count == r.period+1 {
			// Compute initial averages from simple average
			sumGain := 0.0
			sumLoss := 0.0
			for _, g := range r.gains {
				sumGain += g
			}
			for _, l := range r.losses {
				sumLoss += l
			}
			r.avgGain = sumGain / float64(r.period)
			r.avgLoss = sumLoss / float64(r.period)
			r.computeRSI()
			r.ready = true
			// Free seeding slices
			r.gains = nil
			r.losses = nil
		}
		return
	}

	// Wilder's smoothing
	p := float64(r.period)
	r.avgGain = (r.avgGain*(p-1) + gain) / p
	r.avgLoss = (r.avgLoss*(p-1) + loss) / p
	r.computeRSI()
}

func (r *RSI) computeRSI() {
	if r.avgLoss == 0 {
		if r.avgGain == 0 {
			r.value = 50 // no movement
		} else {
			r.value = 100 // all gains
		}
		return
	}
	rs := r.avgGain / r.avgLoss
	r.value = 100 - (100 / (1 + rs))
}

// Value returns the current RSI value (0-100).
func (r *RSI) Value() float64 {
	return r.value
}

// Ready returns true when enough bars have been processed to compute RSI.
func (r *RSI) Ready() bool {
	return r.ready
}

// Count returns the number of bars processed.
func (r *RSI) Count() int {
	return r.count
}
