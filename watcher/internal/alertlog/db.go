// Package alertlog provides SQLite-backed alert logging via a single-writer channel.
// All goroutines send to the channel; one dedicated goroutine owns all DB writes.
package alertlog

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

const schema = `
CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         DATETIME DEFAULT CURRENT_TIMESTAMP,
    ticker     TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    price      REAL,
    message    TEXT,
    vwap       REAL,
    rsi        REAL,
    pnl        REAL
);
CREATE INDEX IF NOT EXISTS idx_alerts_ticker_ts ON alerts(ticker, ts);
`

// Record is one alert to be persisted.
type Record struct {
	Ticker    string
	AlertType string
	Price     float64
	VWAP      float64
	RSI       float64
	PnL       float64
	Message   string
}

// DB owns the SQLite connection and a single write goroutine.
type DB struct {
	db   *sql.DB
	stmt *sql.Stmt
	ch   chan Record
	done chan struct{}
}

// New opens (or creates) the SQLite DB and starts the write goroutine.
func New(dbPath string) (*DB, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("alertlog: open %s: %w", dbPath, err)
	}

	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, fmt.Errorf("alertlog: migrate: %w", err)
	}

	stmt, err := db.Prepare(`
		INSERT INTO alerts (ts, ticker, alert_type, price, message, vwap, rsi, pnl)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		db.Close()
		return nil, fmt.Errorf("alertlog: prepare: %w", err)
	}

	d := &DB{
		db:   db,
		stmt: stmt,
		ch:   make(chan Record, 256), // buffered — callers never block
		done: make(chan struct{}),
	}

	go d.writeLoop()
	log.Printf("[alertlog] opened %s (single-writer channel)", dbPath)
	return d, nil
}

// Log enqueues an alert record for writing. Never blocks the caller.
func (d *DB) Log(ticker, alertType string, price, vwap, rsi, pnl float64, message string) {
	select {
	case d.ch <- Record{ticker, alertType, price, vwap, rsi, pnl, message}:
	default:
		log.Printf("[alertlog] channel full — dropped alert for %s", ticker)
	}
}

// Close drains the channel and shuts down the write goroutine.
func (d *DB) Close() {
	close(d.ch)
	<-d.done
	if d.stmt != nil {
		d.stmt.Close()
	}
	if d.db != nil {
		d.db.Close()
	}
}

// writeLoop is the single goroutine that owns all DB writes.
func (d *DB) writeLoop() {
	defer close(d.done)
	for r := range d.ch {
		ts := time.Now().UTC().Format(time.RFC3339)
		if _, err := d.stmt.Exec(ts, r.Ticker, r.AlertType, r.Price, r.Message, r.VWAP, r.RSI, r.PnL); err != nil {
			log.Printf("[alertlog] write error: %v", err)
		}
	}
}
