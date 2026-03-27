package metrics

// MACD computes the Moving Average Convergence Divergence indicator.
//
// MACD Line = EMA(fast) - EMA(slow)
// Signal Line = EMA(signal) of MACD Line
// Histogram = MACD Line - Signal Line
type MACD struct {
	fastEMA   *EMA
	slowEMA   *EMA
	signalEMA *EMA
	macdLine  float64
	signal    float64
	histogram float64
	ready     bool
}

// NewMACD creates a new MACD calculator (typically 12, 26, 9).
func NewMACD(fast, slow, signal int) *MACD {
	return &MACD{
		fastEMA:   NewEMA(fast),
		slowEMA:   NewEMA(slow),
		signalEMA: NewEMA(signal),
	}
}

// Update adds a new close price and recalculates MACD.
func (m *MACD) Update(close float64) {
	m.fastEMA.Update(close)
	m.slowEMA.Update(close)

	if m.fastEMA.Ready() && m.slowEMA.Ready() {
		m.macdLine = m.fastEMA.Value() - m.slowEMA.Value()
		m.signalEMA.Update(m.macdLine)

		if m.signalEMA.Ready() {
			m.signal = m.signalEMA.Value()
			m.histogram = m.macdLine - m.signal
			m.ready = true
		}
	}
}

// MACDLine returns the MACD line value.
func (m *MACD) MACDLine() float64 {
	return m.macdLine
}

// Signal returns the signal line value.
func (m *MACD) Signal() float64 {
	return m.signal
}

// Histogram returns the histogram value (MACD - Signal).
func (m *MACD) Histogram() float64 {
	return m.histogram
}

// Ready returns true when all three EMAs have been seeded.
func (m *MACD) Ready() bool {
	return m.ready
}
