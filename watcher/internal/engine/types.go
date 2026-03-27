package engine

import "time"

// WatcherState represents the lifecycle state of a watcher goroutine.
type WatcherState int

const (
	StateStarting WatcherState = iota
	StateRunning
	StatePaused
	StateStopped
	StateFailed
)

func (s WatcherState) String() string {
	switch s {
	case StateStarting:
		return "starting"
	case StateRunning:
		return "running"
	case StatePaused:
		return "paused"
	case StateStopped:
		return "stopped"
	case StateFailed:
		return "failed"
	default:
		return "unknown"
	}
}

// EventType represents the type of event emitted by a watcher.
type EventType int

const (
	EventPriceUpdate EventType = iota
	EventAlert
	EventStateChange
	EventPanic
	EventStopped
)

// Event is emitted by a watcher goroutine to the supervisor.
type Event struct {
	Type    EventType
	Ticker  string
	State   WatcherState
	Price   float64
	VWAP    float64
	RSI     float64
	Message string
	Error   interface{}
	Time    time.Time
}

// Command is sent from the supervisor/API to a watcher.
type CommandType int

const (
	CmdStop CommandType = iota
	CmdPause
	CmdResume
	CmdStatus
	CmdUpdateLevels
)

// Command carries an instruction to a watcher.
type Command struct {
	Type   CommandType
	Stop   float64
	Target float64
	Reply  chan CommandReply
}

// CommandReply is the response from a watcher to a command.
type CommandReply struct {
	State   WatcherState
	Price   float64
	VWAP    float64
	RSI     float64
	PnL     float64
	Message string
	Error   string
}
