// Package alertlog provides SQLite-backed alert logging.
// Go writes alerts; the Python bridge reads them (read-only).
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

// DB wraps a SQLite connection for alert logging.
type DB struct {
	db   *sql.DB
	stmt *sql.Stmt
}

// New opens (or creates) the SQLite database at dbPath and runs migrations.
func New(dbPath string) (*DB, error) {
	db, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL&_busy_timeout=5000")
	if err != nil {
		return nil, fmt.Errorf("alertlog: open %s: %w", dbPath, err)
	}

	// Run schema migration
	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, fmt.Errorf("alertlog: migrate: %w", err)
	}

	// Prepare insert statement for performance
	stmt, err := db.Prepare(`
		INSERT INTO alerts (ts, ticker, alert_type, price, message, vwap, rsi, pnl)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		db.Close()
		return nil, fmt.Errorf("alertlog: prepare: %w", err)
	}

	log.Printf("[alertlog] opened %s", dbPath)
	return &DB{db: db, stmt: stmt}, nil
}

// Log inserts an alert row. Timestamps are stored as UTC ISO8601.
func (d *DB) Log(ticker, alertType string, price, vwap, rsi, pnl float64, message string) error {
	ts := time.Now().UTC().Format(time.RFC3339)
	_, err := d.stmt.Exec(ts, ticker, alertType, price, message, vwap, rsi, pnl)
	if err != nil {
		return fmt.Errorf("alertlog: insert: %w", err)
	}
	return nil
}

// Close closes the prepared statement and database connection.
func (d *DB) Close() error {
	if d.stmt != nil {
		d.stmt.Close()
	}
	if d.db != nil {
		return d.db.Close()
	}
	return nil
}
