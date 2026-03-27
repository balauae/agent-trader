package metrics

// VolumeTracker maintains a rolling window of volume values for
// computing the average and detecting volume spikes.
type VolumeTracker struct {
	window  int
	values  []float64
	sum     float64
	count   int
	current float64
}

// NewVolumeTracker creates a new VolumeTracker with the given rolling window size.
func NewVolumeTracker(window int) *VolumeTracker {
	return &VolumeTracker{
		window: window,
		values: make([]float64, 0, window),
	}
}

// Update adds a new volume value to the rolling window.
func (v *VolumeTracker) Update(vol float64) {
	v.current = vol
	v.count++

	if len(v.values) < v.window {
		v.values = append(v.values, vol)
		v.sum += vol
		return
	}

	// Slide the window: remove oldest, add newest
	idx := (v.count - 1) % v.window
	v.sum -= v.values[idx]
	v.values[idx] = vol
	v.sum += vol
}

// Average returns the rolling average volume.
func (v *VolumeTracker) Average() float64 {
	n := len(v.values)
	if n == 0 {
		return 0
	}
	return v.sum / float64(n)
}

// Current returns the most recent volume value.
func (v *VolumeTracker) Current() float64 {
	return v.current
}

// IsSpike returns true if the current volume exceeds average * multiplier.
func (v *VolumeTracker) IsSpike(multiplier float64) bool {
	avg := v.Average()
	if avg == 0 {
		return false
	}
	return v.current >= avg*multiplier
}

// SpikeRatio returns current volume / average volume (0 if no average yet).
func (v *VolumeTracker) SpikeRatio() float64 {
	avg := v.Average()
	if avg == 0 {
		return 0
	}
	return v.current / avg
}

// Ready returns true when the full window has been filled.
func (v *VolumeTracker) Ready() bool {
	return len(v.values) >= v.window
}

// Count returns the total number of values processed.
func (v *VolumeTracker) Count() int {
	return v.count
}
