// Package position defines trade position structures and operations.
package position

// Direction indicates whether a position is long or short.
type Direction string

const (
	Long  Direction = "long"
	Short Direction = "short"
)

// Position represents an open trade position.
type Position struct {
	Ticker   string    `json:"ticker"`
	Exchange string    `json:"exchange,omitempty"` // override exchange prefix (e.g. "NYSE")
	Shares   float64   `json:"shares"`
	AvgPrice float64   `json:"avg_price"`
	Stop     float64   `json:"stop"`
	Target   float64   `json:"target"`
	Dir      Direction `json:"direction,omitempty"` // defaults to "long"
}

// GetDirection returns the position direction, defaulting to Long.
func (p *Position) GetDirection() Direction {
	if p.Dir == Short {
		return Short
	}
	return Long
}

// PnLDollars returns unrealised P&L in dollars.
func (p *Position) PnLDollars(currentPrice float64) float64 {
	diff := currentPrice - p.AvgPrice
	if p.GetDirection() == Short {
		diff = -diff
	}
	return diff * p.Shares
}

// PnLPercent returns unrealised P&L as a percentage.
func (p *Position) PnLPercent(currentPrice float64) float64 {
	if p.AvgPrice == 0 {
		return 0
	}
	diff := currentPrice - p.AvgPrice
	if p.GetDirection() == Short {
		diff = -diff
	}
	return (diff / p.AvgPrice) * 100
}

// StopDistancePct returns how far the current price is from the stop, in percent.
func (p *Position) StopDistancePct(currentPrice float64) float64 {
	if currentPrice == 0 {
		return 0
	}
	if p.GetDirection() == Long {
		return ((currentPrice - p.Stop) / currentPrice) * 100
	}
	return ((p.Stop - currentPrice) / currentPrice) * 100
}

// TargetDistancePct returns how far the current price is from the target, in percent.
func (p *Position) TargetDistancePct(currentPrice float64) float64 {
	if currentPrice == 0 {
		return 0
	}
	if p.GetDirection() == Long {
		return ((p.Target - currentPrice) / currentPrice) * 100
	}
	return ((currentPrice - p.Target) / currentPrice) * 100
}
