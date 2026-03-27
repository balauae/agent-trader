// Package bridge provides a client for the Python FastAPI analysis bridge.
package bridge

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// Client calls the Python FastAPI bridge at localhost:8000.
type Client struct {
	base   string
	client *http.Client
}

// New creates a bridge client.
func New(baseURL string) *Client {
	if baseURL == "" {
		baseURL = "http://localhost:8000"
	}
	return &Client{
		base:   baseURL,
		client: &http.Client{Timeout: 15 * time.Second},
	}
}

// News fetches latest news for a ticker.
func (c *Client) News(ticker string) (map[string]interface{}, error) {
	return c.get("/news/" + ticker)
}

// Analyze fetches technical analysis for a ticker.
func (c *Client) Analyze(ticker string) (map[string]interface{}, error) {
	return c.get("/analyze/" + ticker)
}

// VWAP fetches VWAP analysis for a ticker.
func (c *Client) VWAP(ticker string) (map[string]interface{}, error) {
	return c.get("/vwap/" + ticker)
}

// Pattern fetches chart pattern detection for a ticker.
func (c *Client) Pattern(ticker string) (map[string]interface{}, error) {
	return c.get("/pattern/" + ticker)
}

// Earnings fetches earnings info for a ticker.
func (c *Client) Earnings(ticker string) (map[string]interface{}, error) {
	return c.get("/earnings/" + ticker)
}

// IsUp checks if the bridge is running.
func (c *Client) IsUp() bool {
	resp, err := c.client.Get(c.base + "/health")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == 200
}

func (c *Client) get(path string) (map[string]interface{}, error) {
	resp, err := c.client.Get(c.base + path)
	if err != nil {
		return nil, fmt.Errorf("bridge: %w", err)
	}
	defer resp.Body.Close()
	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("bridge: decode: %w", err)
	}
	if resp.StatusCode != 200 {
		if msg, ok := result["detail"].(string); ok {
			return nil, fmt.Errorf("bridge: %s", msg)
		}
		return nil, fmt.Errorf("bridge: status %d", resp.StatusCode)
	}
	return result, nil
}
