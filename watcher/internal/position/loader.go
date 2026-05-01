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

// SavePositions writes positions back to the JSON file.
func SavePositions(path string, positions []Position) error {
	data, err := json.MarshalIndent(positions, "", "  ")
	if err != nil {
		return fmt.Errorf("position: marshal: %w", err)
	}
	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("position: write %s: %w", path, err)
	}
	return nil
}

// AddPosition appends a position to the file (or updates if ticker exists).
func AddPosition(path string, pos Position) error {
	positions, err := LoadPositions(path)
	if err != nil {
		positions = []Position{}
	}
	// Update if exists, append if new
	found := false
	for i := range positions {
		if positions[i].Ticker == pos.Ticker {
			positions[i] = pos
			found = true
			break
		}
	}
	if !found {
		positions = append(positions, pos)
	}
	return SavePositions(path, positions)
}

// RemovePosition removes a ticker from the positions file.
func RemovePosition(path string, ticker string) error {
	positions, err := LoadPositions(path)
	if err != nil {
		return err
	}
	var updated []Position
	for _, p := range positions {
		if p.Ticker != ticker {
			updated = append(updated, p)
		}
	}
	return SavePositions(path, updated)
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
