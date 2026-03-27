package engine

import (
	"sync"
	"time"

	"github.com/bala/tradedesk-watcher/internal/state"
)

// RegistryEntry holds metadata about a running watcher.
type RegistryEntry struct {
	Ticker    string       `json:"ticker"`
	State     string       `json:"state"`
	StartedAt time.Time    `json:"started_at"`
	Stop      float64      `json:"stop"`
	Target    float64      `json:"target"`
	AvgPrice  float64      `json:"avg_price"`
	Restarts  int          `json:"restarts"`
}

// Registry tracks all active watcher goroutines.
type Registry struct {
	mu       sync.RWMutex
	entries  map[string]*RegistryEntry
	savePath string
}

// NewRegistry creates a new registry that persists to the given path.
func NewRegistry(savePath string) *Registry {
	return &Registry{
		entries:  make(map[string]*RegistryEntry),
		savePath: savePath,
	}
}

// Register adds or updates an entry.
func (r *Registry) Register(ticker string, entry *RegistryEntry) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.entries[ticker] = entry
	r.save()
}

// Remove deletes an entry.
func (r *Registry) Remove(ticker string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.entries, ticker)
	r.save()
}

// Get returns the entry for a ticker.
func (r *Registry) Get(ticker string) (*RegistryEntry, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	e, ok := r.entries[ticker]
	return e, ok
}

// List returns all registry entries.
func (r *Registry) List() map[string]*RegistryEntry {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make(map[string]*RegistryEntry, len(r.entries))
	for k, v := range r.entries {
		out[k] = v
	}
	return out
}

// UpdateState updates the state of an entry.
func (r *Registry) UpdateState(ticker string, s WatcherState) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if e, ok := r.entries[ticker]; ok {
		e.State = s.String()
		r.save()
	}
}

// IncrementRestarts increments the restart counter.
func (r *Registry) IncrementRestarts(ticker string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if e, ok := r.entries[ticker]; ok {
		e.Restarts++
		r.save()
	}
}

func (r *Registry) save() {
	if r.savePath == "" {
		return
	}
	type registryFile struct {
		Watchers map[string]*RegistryEntry `json:"watchers"`
	}
	_ = state.WriteAtomic(r.savePath, registryFile{Watchers: r.entries})
}
