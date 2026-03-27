BINARY=../bin/tradedesk-watcher
GO=/usr/local/go/bin/go

build:
	$(GO) build -o $(BINARY) ./cmd/watcher
	@echo "✅ Built $(BINARY)"

deploy: build
	systemctl --user restart tradedesk-watcher
	@echo "✅ Deployed and restarted"

logs:
	journalctl --user -u tradedesk-watcher -f

status:
	systemctl --user status tradedesk-watcher --no-pager

stop:
	systemctl --user stop tradedesk-watcher

start:
	systemctl --user start tradedesk-watcher
