// Package config loads watcher settings from JSON and environment variables.
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// Settings holds all watcher configuration.
type Settings struct {
	PollIntervalMs    int           `json:"poll_interval_ms"`
	AlertCooldownMins int           `json:"alert_cooldown_mins"`
	SocketPath        string        `json:"socket_path"`
	DataDir           string        `json:"data_dir"`
	PositionsFile     string        `json:"positions_file"`
	SecretsDir        string        `json:"secrets_dir"`
	RSIPeriod         int           `json:"rsi_period"`
	ATRPeriod         int           `json:"atr_period"`
	EMAShort          int           `json:"ema_short"`
	EMALong           int           `json:"ema_long"`
	MACDFast          int           `json:"macd_fast"`
	MACDSlow          int           `json:"macd_slow"`
	MACDSignal        int           `json:"macd_signal"`
	VolumeWindow      int           `json:"volume_window"`
	VolumeSpikeMulti  float64       `json:"volume_spike_multiplier"`
	NumBars           int           `json:"num_bars"`
	Timezone          string        `json:"timezone"`
	PollInterval      time.Duration `json:"-"`
	AlertCooldown     time.Duration `json:"-"`
}

// DefaultSettings returns sensible defaults for Phase 1.
func DefaultSettings() *Settings {
	return &Settings{
		PollIntervalMs:    1000,
		AlertCooldownMins: 15,
		SocketPath:        "/run/tradedesk/manager.sock",
		DataDir:           "data",
		PositionsFile:     "data/positions.json",
		SecretsDir:        ".secrets",
		RSIPeriod:         14,
		ATRPeriod:         14,
		EMAShort:          9,
		EMALong:           20,
		MACDFast:          12,
		MACDSlow:          26,
		MACDSignal:        9,
		VolumeWindow:      20,
		VolumeSpikeMulti:  2.0,
		NumBars:           300,
		Timezone:          "Asia/Dubai",
		PollInterval:      time.Second,
		AlertCooldown:     15 * time.Minute,
	}
}

// Load reads settings from a JSON file, falling back to defaults for missing fields.
func Load(path string) (*Settings, error) {
	s := DefaultSettings()

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			// No config file, use defaults
			return s, nil
		}
		return nil, fmt.Errorf("config: read %s: %w", path, err)
	}

	if err := json.Unmarshal(data, s); err != nil {
		return nil, fmt.Errorf("config: parse %s: %w", path, err)
	}

	// Apply env overrides
	if v := os.Getenv("WATCHER_POSITIONS_FILE"); v != "" {
		s.PositionsFile = v
	}
	if v := os.Getenv("WATCHER_SECRETS_DIR"); v != "" {
		s.SecretsDir = v
	}
	if v := os.Getenv("WATCHER_DATA_DIR"); v != "" {
		s.DataDir = v
	}
	if v := os.Getenv("WATCHER_SOCKET"); v != "" {
		s.SocketPath = v
	}

	// Compute durations
	s.PollInterval = time.Duration(s.PollIntervalMs) * time.Millisecond
	s.AlertCooldown = time.Duration(s.AlertCooldownMins) * time.Minute

	return s, nil
}

// LoadAuthToken reads the TradingView auth token from the secrets directory.
func LoadAuthToken(secretsDir string) (string, error) {
	path := filepath.Join(secretsDir, "tradingview.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("config: read token: %w", err)
	}

	var creds struct {
		AuthToken string `json:"auth_token"`
	}
	if err := json.Unmarshal(data, &creds); err != nil {
		return "", fmt.Errorf("config: parse token: %w", err)
	}
	if creds.AuthToken == "" {
		return "", fmt.Errorf("config: auth_token is empty in %s", path)
	}
	return creds.AuthToken, nil
}
