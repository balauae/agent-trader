// Package store provides DuckDB-backed bar persistence for the watcher.
// It reads historical bars for startup seeding and writes live bars from TradingView.
package store

import (
	"database/sql"
	"fmt"
	"log"
	"sync"
	"time"

	_ "github.com/marcboeker/go-duckdb"
)

// Bar holds OHLCV data for a single bar.
type Bar struct {
	Timestamp time.Time
	Open      float64
	High      float64
	Low       float64
	Close     float64
	Volume    float64
}

// BarStore wraps a DuckDB connection for bar reads/writes.
type BarStore struct {
	db   *sql.DB
	mu   sync.Mutex // serialise writes — DuckDB doesn't handle concurrent writers well
	path string
}

// NewBarStore opens an existing DuckDB database.
// It does NOT create tables — those are managed by the Python loader.
func NewBarStore(dbPath string) (*BarStore, error) {
	dsn := dbPath + "?access_mode=READ_WRITE"
	db, err := sql.Open("duckdb", dsn)
	if err != nil {
		return nil, fmt.Errorf("duckdb: open %s: %w", dbPath, err)
	}

	// Verify connectivity
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("duckdb: ping %s: %w", dbPath, err)
	}

	log.Printf("[duckdb] opened %s", dbPath)
	return &BarStore{db: db, path: dbPath}, nil
}

// Close shuts down the DuckDB connection.
func (s *BarStore) Close() error {
	return s.db.Close()
}

// LoadBars loads the last `limit` bars for a ticker+timeframe, ordered by ts ASC (oldest first).
// Used for startup seeding of metrics.
func (s *BarStore) LoadBars(ticker, timeframe string, limit int) ([]Bar, error) {
	// Subquery to get latest N rows, then re-sort ASC
	query := `
		SELECT ts, open, high, low, "close", volume
		FROM (
			SELECT ts, open, high, low, "close", volume
			FROM bars
			WHERE ticker = $1 AND timeframe = $2
			ORDER BY ts DESC
			LIMIT $3
		) sub
		ORDER BY ts ASC
	`

	rows, err := s.db.Query(query, ticker, timeframe, limit)
	if err != nil {
		return nil, fmt.Errorf("duckdb: load bars %s/%s: %w", ticker, timeframe, err)
	}
	defer rows.Close()

	var bars []Bar
	for rows.Next() {
		var b Bar
		if err := rows.Scan(&b.Timestamp, &b.Open, &b.High, &b.Low, &b.Close, &b.Volume); err != nil {
			return nil, fmt.Errorf("duckdb: scan bar: %w", err)
		}
		bars = append(bars, b)
	}
	return bars, rows.Err()
}

// WriteBars upserts bars into DuckDB for a given ticker+timeframe.
// Uses INSERT OR REPLACE on the primary key (ticker, timeframe, ts).
func (s *BarStore) WriteBars(ticker, timeframe string, bars []Bar) error {
	if len(bars) == 0 {
		return nil
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	tx, err := s.db.Begin()
	if err != nil {
		return fmt.Errorf("duckdb: begin tx: %w", err)
	}

	stmt, err := tx.Prepare(`
		INSERT OR REPLACE INTO bars (ticker, timeframe, ts, open, high, low, "close", volume)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
	`)
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("duckdb: prepare upsert: %w", err)
	}
	defer stmt.Close()

	for _, b := range bars {
		if _, err := stmt.Exec(ticker, timeframe, b.Timestamp, b.Open, b.High, b.Low, b.Close, b.Volume); err != nil {
			tx.Rollback()
			return fmt.Errorf("duckdb: insert bar: %w", err)
		}
	}

	return tx.Commit()
}
