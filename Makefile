# FRIDAY — all commands
# Usage: make <target>

VENV    := .venv/bin/python
PY      := PYTHONPATH=. $(VENV)
BVENV   := cd backend && PYTHONPATH=. ../.venv/bin/python
BUVICORN := cd backend && PYTHONPATH=. ../.venv/bin/uvicorn

.PHONY: setup start stop status app build-app xcode test ask health listen \
        db-init db-shell backend-start backend-stop backend-health \
        backend-sync clean

# ─── Setup ────────────────────────────────────────────────────────────────────

setup:
	bash scripts/setup.sh

# ─── Runtime (port 7700) ──────────────────────────────────────────────────────

start:
	bash scripts/start.sh

stop:
	@lsof -ti :7700 2>/dev/null | xargs kill 2>/dev/null && echo "Runtime stopped." || echo "Runtime was not running."

status:
	@echo "=== Runtime (7700) ===" && curl -s http://127.0.0.1:7700/health || echo "  not running"
	@echo "=== Backend (7800) ===" && curl -s http://127.0.0.1:7800/health || echo "  not running"

health:
	$(PY) -m runtime.cli --health

listen:
	$(PY) -m runtime.cli --listen

ask:
	@read -p "Command: " cmd; $(PY) -m runtime.cli "$$cmd"

# ─── Swift App ────────────────────────────────────────────────────────────────

app:
	bash scripts/run_app.sh

build-app:
	cd apps/macos && swift build -c release

xcode:
	open apps/macos/Package.swift

# ─── Backend (port 7800) ──────────────────────────────────────────────────────

backend-start:
	@echo "Starting FRIDAY backend on http://127.0.0.1:7800..."
	$(BUVICORN) app.main:app --port 7800 --log-level info &

backend-stop:
	@lsof -ti :7800 2>/dev/null | xargs kill 2>/dev/null && echo "Backend stopped." || echo "Backend was not running."

backend-health:
	@curl -s http://127.0.0.1:7800/health | python3 -m json.tool

backend-sync:
	@curl -s -H "Authorization: Bearer $$(grep FRIDAY_BACKEND_KEY backend/.env | cut -d= -f2)" \
	  http://127.0.0.1:7800/sync/status | python3 -m json.tool

# ─── Database ─────────────────────────────────────────────────────────────────

db-init:
	$(PY) -c "from database.db import init_db; init_db(); print('DB ready at ~/.friday/friday.db')"

db-shell:
	sqlite3 ~/.friday/friday.db

# ─── Testing ──────────────────────────────────────────────────────────────────

test:
	PYTHONPATH=. .venv/bin/pytest tests/ -v

# ─── Cleanup ──────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	cd apps/macos && swift package clean 2>/dev/null; true
