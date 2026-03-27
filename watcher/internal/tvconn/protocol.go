package tvconn

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// WrapMsg wraps a message string in the TradingView ~m~ framing protocol.
func WrapMsg(msg string) string {
	return fmt.Sprintf("~m~%d~m~%s", len(msg), msg)
}

// BuildPayload creates a JSON-encoded TV command payload.
func BuildPayload(funcName string, args []interface{}) (string, error) {
	payload := map[string]interface{}{
		"m": funcName,
		"p": args,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("protocol: marshal %s: %w", funcName, err)
	}
	return string(data), nil
}

// IsHeartbeat returns true if the raw message contains a heartbeat (~h~).
func IsHeartbeat(raw string) bool {
	return strings.Contains(raw, "~h~")
}

// ExtractHeartbeats returns all heartbeat tokens from a raw message.
func ExtractHeartbeats(raw string) []string {
	var beats []string
	parts := strings.Split(raw, "~m~")
	for _, p := range parts {
		if strings.HasPrefix(p, "~h~") {
			beats = append(beats, p)
		}
	}
	return beats
}

// ParseMessages splits a raw WebSocket frame into individual JSON message strings.
func ParseMessages(raw string) []string {
	var msgs []string
	parts := strings.Split(raw, "~m~")
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if strings.HasPrefix(part, "{") {
			msgs = append(msgs, part)
		}
	}
	return msgs
}

// ParseTVMessage parses a single JSON message string into a Message struct.
func ParseTVMessage(jsonStr string) (*Message, error) {
	var parsed map[string]interface{}
	if err := json.Unmarshal([]byte(jsonStr), &parsed); err != nil {
		return nil, fmt.Errorf("protocol: parse json: %w", err)
	}

	method, _ := parsed["m"].(string)
	args, _ := parsed["p"].([]interface{})

	msg := &Message{
		Method:  method,
		RawArgs: args,
	}

	switch method {
	case "qsd":
		msg.Quote = parseQuote(args)
	case "du":
		msg.SeriesUpdate = parseSeriesUpdate(args)
	}

	return msg, nil
}

func parseQuote(args []interface{}) *Quote {
	if len(args) < 2 {
		return nil
	}
	data, ok := args[1].(map[string]interface{})
	if !ok {
		return nil
	}

	name, _ := data["n"].(string)
	v, ok := data["v"].(map[string]interface{})
	if !ok {
		return nil
	}

	q := &Quote{
		Ticker:    name,
		Price:     toFloat(v["lp"]),
		Change:    toFloat(v["ch"]),
		ChangePct: toFloat(v["chp"]),
		Volume:    toFloat(v["volume"]),
		Bid:       toFloat(v["bid"]),
		Ask:       toFloat(v["ask"]),
		Time:      time.Now(),
	}

	// Only return if we have a price
	if q.Price == 0 {
		// Try "rtc" (real-time close) as fallback
		if rtc := toFloat(v["rtc"]); rtc != 0 {
			q.Price = rtc
		}
	}

	return q
}

func parseSeriesUpdate(args []interface{}) *SeriesUpdate {
	if len(args) < 2 {
		return nil
	}
	seriesData, ok := args[1].(map[string]interface{})
	if !ok {
		return nil
	}

	su := &SeriesUpdate{}

	for _, v := range seriesData {
		barsMap, ok := v.(map[string]interface{})
		if !ok {
			continue
		}
		s, ok := barsMap["s"].([]interface{})
		if !ok {
			continue
		}

		for _, barEntry := range s {
			barMap, ok := barEntry.(map[string]interface{})
			if !ok {
				continue
			}
			vals, ok := barMap["v"].([]interface{})
			if !ok || len(vals) < 6 {
				continue
			}

			ts := int64(toFloat(vals[0]))
			bar := Bar{
				Time:   time.Unix(ts, 0),
				Open:   toFloat(vals[1]),
				High:   toFloat(vals[2]),
				Low:    toFloat(vals[3]),
				Close:  toFloat(vals[4]),
				Volume: toFloat(vals[5]),
			}
			su.Bars = append(su.Bars, bar)
		}
	}

	return su
}

func toFloat(v interface{}) float64 {
	if v == nil {
		return 0
	}
	switch val := v.(type) {
	case float64:
		return val
	case int:
		return float64(val)
	case int64:
		return float64(val)
	case string:
		f, _ := strconv.ParseFloat(val, 64)
		return f
	case json.Number:
		f, _ := val.Float64()
		return f
	}
	return 0
}
