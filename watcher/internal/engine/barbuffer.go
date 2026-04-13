package engine

import "math"

// Bar holds OHLCV data for a single bar, mirroring tvconn.Bar but without
// the import dependency (we only store the numeric fields we need).
type Bar struct {
	High   float64
	Low    float64
	Close  float64
	Volume float64
}

// BarBuffer is a bounded circular buffer of recent bars.
// It stores at most `size` bars and provides ordered access for
// computing Bollinger Bands, support/resistance, and other window-based metrics.
type BarBuffer struct {
	bars []Bar
	size int
	pos  int
	full bool
}

// NewBarBuffer creates a new bar buffer with the given capacity.
func NewBarBuffer(size int) *BarBuffer {
	return &BarBuffer{
		bars: make([]Bar, size),
		size: size,
	}
}

// Add appends a bar to the buffer, overwriting the oldest if full.
func (b *BarBuffer) Add(bar Bar) {
	b.bars[b.pos] = bar
	b.pos = (b.pos + 1) % b.size
	if !b.full && b.pos == 0 {
		b.full = true
	}
}

// Len returns the number of bars currently stored.
func (b *BarBuffer) Len() int {
	if b.full {
		return b.size
	}
	return b.pos
}

// Slice returns the bars in chronological order (oldest first).
func (b *BarBuffer) Slice() []Bar {
	n := b.Len()
	out := make([]Bar, n)
	if b.full {
		// pos points to the oldest entry
		copy(out, b.bars[b.pos:])
		copy(out[b.size-b.pos:], b.bars[:b.pos])
	} else {
		copy(out, b.bars[:b.pos])
	}
	return out
}

// LastN returns the most recent N bars in chronological order.
// If fewer than N bars exist, returns all available.
func (b *BarBuffer) LastN(n int) []Bar {
	total := b.Len()
	if n > total {
		n = total
	}
	all := b.Slice()
	return all[total-n:]
}

// BollingerBands computes SMA(period) and upper/lower bands (SMA +/- mult*stddev)
// from the close prices in the buffer.
func (b *BarBuffer) BollingerBands(period int, mult float64) (mid, upper, lower float64) {
	bars := b.LastN(period)
	n := len(bars)
	if n == 0 {
		return 0, 0, 0
	}

	// SMA
	sum := 0.0
	for _, bar := range bars {
		sum += bar.Close
	}
	mid = sum / float64(n)

	// Standard deviation
	sumSq := 0.0
	for _, bar := range bars {
		diff := bar.Close - mid
		sumSq += diff * diff
	}
	stddev := math.Sqrt(sumSq / float64(n))

	upper = mid + mult*stddev
	lower = mid - mult*stddev
	return
}

// SMA computes a simple moving average of close prices over the last `period` bars.
func (b *BarBuffer) SMA(period int) float64 {
	bars := b.LastN(period)
	n := len(bars)
	if n == 0 {
		return 0
	}
	sum := 0.0
	for _, bar := range bars {
		sum += bar.Close
	}
	return sum / float64(n)
}

// SupportResistance returns support (min low) and resistance (max high)
// over the last `period` bars.
func (b *BarBuffer) SupportResistance(period int) (support, resistance float64) {
	bars := b.LastN(period)
	if len(bars) == 0 {
		return 0, 0
	}
	support = bars[0].Low
	resistance = bars[0].High
	for _, bar := range bars[1:] {
		if bar.Low < support {
			support = bar.Low
		}
		if bar.High > resistance {
			resistance = bar.High
		}
	}
	return
}
