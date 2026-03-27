package main

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"strings"
	"time"

	"github.com/gorilla/websocket"
)

const (
	tvWSURL = "wss://data.tradingview.com/socket.io/websocket"
)

// TradingView message wrapper
func wrapMsg(msg string) string {
	return fmt.Sprintf("~m~%d~m~%s", len(msg), msg)
}

// Random session ID (like browser)
func randomSession(prefix string) string {
	const chars = "abcdefghijklmnopqrstuvwxyz0123456789"
	b := make([]byte, 12)
	for i := range b {
		b[i] = chars[rand.Intn(len(chars))]
	}
	return prefix + "_" + string(b)
}

func sendMsg(conn *websocket.Conn, funcName string, args []interface{}) error {
	payload := map[string]interface{}{
		"m": funcName,
		"p": args,
	}
	data, _ := json.Marshal(payload)
	msg := wrapMsg(string(data))
	return conn.WriteMessage(websocket.TextMessage, []byte(msg))
}

func main() {
	ticker := "MRVL"
	if len(os.Args) > 1 {
		ticker = strings.ToUpper(os.Args[1])
	}

	// Load auth token
	tokenFile := "../../.secrets/tradingview.json"
	data, err := os.ReadFile(tokenFile)
	if err != nil {
		fmt.Println("❌ Could not read token file:", err)
		os.Exit(1)
	}
	var creds map[string]interface{}
	json.Unmarshal(data, &creds)
	authToken := creds["auth_token"].(string)

	fmt.Printf("🔌 Connecting to TradingView WebSocket...\n")
	fmt.Printf("📈 Ticker: %s\n\n", ticker)

	// Connect
	dialer := websocket.DefaultDialer
	headers := map[string][]string{
		"Origin":  {"https://data.tradingview.com"},
		"Referer": {"https://www.tradingview.com"},
	}
	conn, _, err := dialer.Dial(tvWSURL, headers)
	if err != nil {
		fmt.Println("❌ Connection failed:", err)
		os.Exit(1)
	}
	defer conn.Close()
	fmt.Println("✅ Connected!")

	// Sessions
	chartSession := randomSession("cs")
	quoteSession := randomSession("qs")

	// Step 1: Auth
	sendMsg(conn, "set_auth_token", []interface{}{authToken})
	time.Sleep(100 * time.Millisecond)

	// Step 2: Chart session
	sendMsg(conn, "chart_create_session", []interface{}{chartSession, ""})
	time.Sleep(100 * time.Millisecond)

	// Step 3: Quote session
	sendMsg(conn, "quote_create_session", []interface{}{quoteSession})
	time.Sleep(100 * time.Millisecond)

	// Step 4: Add ticker to quote session
	sendMsg(conn, "quote_add_symbols", []interface{}{
		quoteSession,
		fmt.Sprintf("NASDAQ:%s", ticker),
		map[string]interface{}{"flags": []string{"force_permission"}},
	})
	time.Sleep(100 * time.Millisecond)

	// Step 5: Resolve symbol
	sendMsg(conn, "resolve_symbol", []interface{}{
		chartSession,
		"sds_sym_1",
		fmt.Sprintf(`={"symbol":"NASDAQ:%s","adjustment":"splits","session":"extended"}`, ticker),
	})
	time.Sleep(100 * time.Millisecond)

	// Step 6: Create series (1m bars)
	sendMsg(conn, "create_series", []interface{}{
		chartSession, "sds_1", "s1", "sds_sym_1", "1", 10, "",
	})

	fmt.Printf("👂 Listening for %s ticks...\n\n", ticker)

	// Read loop
	timeout := time.After(30 * time.Second)
	for {
		select {
		case <-timeout:
			fmt.Println("\n⏱️ 30s timeout — POC complete")
			return
		default:
			conn.SetReadDeadline(time.Now().Add(5 * time.Second))
			_, msg, err := conn.ReadMessage()
			if err != nil {
				if !strings.Contains(err.Error(), "timeout") {
					fmt.Println("Read error:", err)
				}
				continue
			}

			raw := string(msg)

			// Heartbeat
			if strings.Contains(raw, "~h~") {
				parts := strings.Split(raw, "~m~")
				for _, p := range parts {
					if strings.HasPrefix(p, "~h~") {
						conn.WriteMessage(websocket.TextMessage, []byte(wrapMsg(p)))
					}
				}
				continue
			}

			// Extract JSON parts
			parts := strings.Split(raw, "~m~")
			for _, part := range parts {
				if !strings.HasPrefix(part, "{") {
					continue
				}

				var parsed map[string]interface{}
				if err := json.Unmarshal([]byte(part), &parsed); err != nil {
					continue
				}

				m, _ := parsed["m"].(string)
				p, _ := parsed["p"].([]interface{})

				switch m {
				case "qsd": // Quote data
					if len(p) >= 2 {
						if data, ok := p[1].(map[string]interface{}); ok {
							if v, ok := data["v"].(map[string]interface{}); ok {
								price := v["lp"]
								volume := v["volume"]
								change := v["ch"]
								changePct := v["chp"]
								if price != nil {
									fmt.Printf("💰 %s | Price: $%.2f | Change: %.2f (%.2f%%) | Volume: %.0f\n",
										ticker,
										toFloat(price),
										toFloat(change),
										toFloat(changePct),
										toFloat(volume),
									)
								}
							}
						}
					}

				case "du": // Bar data update — extract OHLCV
					if len(p) >= 2 {
						if series, ok := p[1].(map[string]interface{}); ok {
							for _, v := range series {
								if bars, ok := v.(map[string]interface{}); ok {
									if s, ok := bars["s"].([]interface{}); ok && len(s) > 0 {
										if bar, ok := s[len(s)-1].(map[string]interface{}); ok {
											if vals, ok := bar["v"].([]interface{}); ok && len(vals) >= 5 {
												ts := time.Unix(int64(toFloat(vals[0])), 0).Format("15:04:05")
												o := toFloat(vals[1])
												h := toFloat(vals[2])
												l := toFloat(vals[3])
												c := toFloat(vals[4])
												vol := toFloat(vals[5])
												fmt.Printf("📊 MU | %s | O:$%.2f H:$%.2f L:$%.2f C:$%.2f | Vol:%.0f\n", ts, o, h, l, c, vol)
											}
										}
									}
								}
							}
						}
					}

				case "series_error":
					fmt.Printf("⚠️ Series error: %v\n", p)
				}
			}
		}
	}
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
	}
	return 0
}
