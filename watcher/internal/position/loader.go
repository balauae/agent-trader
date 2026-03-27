package position

import (
	"encoding/json"
	"fmt"
	"os"
)

// LoadPositions reads a JSON file containing an array of positions.
func LoadPositions(path string) ([]Position, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("position: read %s: %w", path, err)
	}

	var positions []Position
	if err := json.Unmarshal(data, &positions); err != nil {
		return nil, fmt.Errorf("position: parse %s: %w", path, err)
	}

	// Default direction to "long" if not specified
	for i := range positions {
		if positions[i].Dir == "" {
			positions[i].Dir = Long
		}
	}

	return positions, nil
}

// FindByTicker returns the position matching the given ticker, or nil.
func FindByTicker(positions []Position, ticker string) *Position {
	for i := range positions {
		if positions[i].Ticker == ticker {
			return &positions[i]
		}
	}
	return nil
}
