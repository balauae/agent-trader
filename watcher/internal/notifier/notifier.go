package notifier

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

// Notifier sends messages to Telegram.
type Notifier struct {
	botToken string
	chatID   string
	client   *http.Client
	queue    chan string
	done     chan struct{}
}

type telegramCreds struct {
	BotToken string `json:"bot_token"`
	ChatID   string `json:"chat_id"`
}

// New loads credentials from secretsDir and returns a Notifier.
func New(secretsDir string) (*Notifier, error) {
	data, err := os.ReadFile(secretsDir + "/telegram.json")
	if err != nil {
		return nil, fmt.Errorf("notifier: read creds: %w", err)
	}
	var creds telegramCreds
	if err := json.Unmarshal(data, &creds); err != nil {
		return nil, fmt.Errorf("notifier: parse creds: %w", err)
	}

	n := &Notifier{
		botToken: creds.BotToken,
		chatID:   creds.ChatID,
		client:   &http.Client{Timeout: 10 * time.Second},
		queue:    make(chan string, 50),
		done:     make(chan struct{}),
	}
	go n.drainQueue()
	return n, nil
}

// Send queues a message for delivery (non-blocking).
func (n *Notifier) Send(msg string) {
	select {
	case n.queue <- msg:
	default:
		// Drop if queue full
	}
}

// SendNow sends a message immediately (blocking, for critical alerts).
func (n *Notifier) SendNow(msg string) error {
	return n.sendTelegram(msg)
}

// Close shuts down the notifier.
func (n *Notifier) Close() {
	close(n.done)
}

func (n *Notifier) drainQueue() {
	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()
	var batch []string

	flush := func() {
		if len(batch) == 0 {
			return
		}
		msg := ""
		for _, m := range batch {
			msg += m + "\n"
		}
		for attempt := 0; attempt < 3; attempt++ {
			if err := n.sendTelegram(msg); err == nil {
				break
			}
			time.Sleep(time.Duration(1<<attempt) * time.Second)
		}
		batch = batch[:0]
	}

	for {
		select {
		case <-n.done:
			flush()
			return
		case msg := <-n.queue:
			batch = append(batch, msg)
			if len(batch) >= 5 {
				flush()
			}
		case <-ticker.C:
			flush()
		}
	}
}

func (n *Notifier) sendTelegram(text string) error {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", n.botToken)
	payload := map[string]string{
		"chat_id":    n.chatID,
		"text":       text,
		"parse_mode": "HTML",
	}
	data, _ := json.Marshal(payload)
	resp, err := n.client.Post(url, "application/json", bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("notifier: post: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("notifier: telegram returned %d", resp.StatusCode)
	}
	return nil
}
