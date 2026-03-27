package tvconn

import (
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

const (
	tvWSURL = "wss://data.tradingview.com/socket.io/websocket"
)

// Conn manages a TradingView WebSocket connection.
type Conn struct {
	ws           *websocket.Conn
	authToken    string
	chartSession string
	quoteSession string
	mu           sync.Mutex
	quoteCh      chan *Quote
	barCh        chan *SeriesUpdate
	errCh        chan error
	done         chan struct{}
}

// ConnOption configures a connection.
type ConnOption func(*Conn)

// WithBufferSize sets the channel buffer sizes.
func WithBufferSize(size int) ConnOption {
	return func(c *Conn) {
		c.quoteCh = make(chan *Quote, size)
		c.barCh = make(chan *SeriesUpdate, size)
	}
}

// Connect establishes a WebSocket connection to TradingView.
func Connect(authToken string, opts ...ConnOption) (*Conn, error) {
	c := &Conn{
		authToken: authToken,
		quoteCh:   make(chan *Quote, 100),
		barCh:     make(chan *SeriesUpdate, 100),
		errCh:     make(chan error, 10),
		done:      make(chan struct{}),
	}

	for _, opt := range opts {
		opt(c)
	}

	dialer := websocket.DefaultDialer
	headers := http.Header{
		"Origin":  {"https://data.tradingview.com"},
		"Referer": {"https://www.tradingview.com"},
	}

	ws, _, err := dialer.Dial(tvWSURL, headers)
	if err != nil {
		return nil, fmt.Errorf("tvconn: dial: %w", err)
	}
	c.ws = ws

	c.chartSession = randomSession("cs")
	c.quoteSession = randomSession("qs")

	// Auth
	if err := c.sendMsg("set_auth_token", []interface{}{authToken}); err != nil {
		ws.Close()
		return nil, fmt.Errorf("tvconn: auth: %w", err)
	}
	time.Sleep(100 * time.Millisecond)

	// Create sessions
	if err := c.sendMsg("chart_create_session", []interface{}{c.chartSession, ""}); err != nil {
		ws.Close()
		return nil, fmt.Errorf("tvconn: chart session: %w", err)
	}
	time.Sleep(100 * time.Millisecond)

	if err := c.sendMsg("quote_create_session", []interface{}{c.quoteSession}); err != nil {
		ws.Close()
		return nil, fmt.Errorf("tvconn: quote session: %w", err)
	}
	time.Sleep(100 * time.Millisecond)

	return c, nil
}

// Subscribe adds a ticker to both the quote and chart sessions.
func (c *Conn) Subscribe(ticker, exchange string, numBars int) error {
	symbol := fmt.Sprintf("%s:%s", exchange, ticker)

	// Add to quote session
	if err := c.sendMsg("quote_add_symbols", []interface{}{
		c.quoteSession,
		symbol,
		map[string]interface{}{"flags": []string{"force_permission"}},
	}); err != nil {
		return fmt.Errorf("tvconn: quote subscribe: %w", err)
	}
	time.Sleep(100 * time.Millisecond)

	// Resolve symbol for chart session
	if err := c.sendMsg("resolve_symbol", []interface{}{
		c.chartSession,
		"sds_sym_1",
		fmt.Sprintf(`={"symbol":"%s","adjustment":"splits","session":"extended"}`, symbol),
	}); err != nil {
		return fmt.Errorf("tvconn: resolve symbol: %w", err)
	}
	time.Sleep(100 * time.Millisecond)

	// Create 1-minute series
	if err := c.sendMsg("create_series", []interface{}{
		c.chartSession, "sds_1", "s1", "sds_sym_1", "1", numBars, "",
	}); err != nil {
		return fmt.Errorf("tvconn: create series: %w", err)
	}

	return nil
}

// Quotes returns the channel for receiving real-time quotes.
func (c *Conn) Quotes() <-chan *Quote {
	return c.quoteCh
}

// Bars returns the channel for receiving bar (OHLCV) updates.
func (c *Conn) Bars() <-chan *SeriesUpdate {
	return c.barCh
}

// Errors returns the channel for receiving connection errors.
func (c *Conn) Errors() <-chan error {
	return c.errCh
}

// Done returns a channel that's closed when the connection is closed.
func (c *Conn) Done() <-chan struct{} {
	return c.done
}

// ReadLoop reads messages from the WebSocket and dispatches them.
// It blocks until the connection is closed or an error occurs.
func (c *Conn) ReadLoop() {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("tvconn: ReadLoop recovered from panic: %v", r)
		}
	}()
	defer close(c.done)
	for {
		c.ws.SetReadDeadline(time.Now().Add(10 * time.Second))
		_, msg, err := c.ws.ReadMessage()
		if err != nil {
			if strings.Contains(err.Error(), "timeout") || strings.Contains(err.Error(), "i/o timeout") {
				continue
			}
			select {
			case c.errCh <- fmt.Errorf("tvconn: read: %w", err):
			default:
			}
			return
		}

		raw := string(msg)

		// Handle heartbeat
		if IsHeartbeat(raw) {
			for _, beat := range ExtractHeartbeats(raw) {
				c.mu.Lock()
				c.ws.WriteMessage(websocket.TextMessage, []byte(WrapMsg(beat)))
				c.mu.Unlock()
			}
			// Also process any non-heartbeat messages in the same frame
			if !strings.HasPrefix(strings.TrimSpace(raw), "~m~") || !IsHeartbeat(raw) {
				continue
			}
		}

		// Parse JSON messages from the frame
		jsonMsgs := ParseMessages(raw)
		for _, jsonStr := range jsonMsgs {
			tvMsg, err := ParseTVMessage(jsonStr)
			if err != nil {
				log.Printf("tvconn: parse error: %v", err)
				continue
			}

			switch tvMsg.Method {
			case "qsd":
				if tvMsg.Quote != nil {
					select {
					case c.quoteCh <- tvMsg.Quote:
					default:
						// Drop if channel full
					}
				}
			case "du":
				if tvMsg.SeriesUpdate != nil && len(tvMsg.SeriesUpdate.Bars) > 0 {
					select {
					case c.barCh <- tvMsg.SeriesUpdate:
					default:
					}
				}
			case "series_error":
				log.Printf("tvconn: series error: %v", tvMsg.RawArgs)
			}
		}
	}
}

// Close shuts down the WebSocket connection.
func (c *Conn) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.ws.Close()
}

// sendMsg sends a framed TV protocol message.
func (c *Conn) sendMsg(funcName string, args []interface{}) error {
	payload, err := BuildPayload(funcName, args)
	if err != nil {
		return err
	}
	wrapped := WrapMsg(payload)
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.ws.WriteMessage(websocket.TextMessage, []byte(wrapped))
}

// randomSession generates a random session ID with the given prefix.
func randomSession(prefix string) string {
	const chars = "abcdefghijklmnopqrstuvwxyz0123456789"
	b := make([]byte, 12)
	for i := range b {
		b[i] = chars[rand.Intn(len(chars))]
	}
	return prefix + "_" + string(b)
}
