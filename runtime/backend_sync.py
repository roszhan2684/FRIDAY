"""Background sync client — pushes local SQLite data to the FRIDAY backend.

Runs as a background thread. Every 5 minutes, syncs:
  - New interaction events
  - New correction logs
  - Updated aliases
  - Reminders
  - Shopping items

Gracefully disabled when FRIDAY_BACKEND_URL is not set.
Idempotent: the backend upserts by id, so re-syncing is safe.
"""
from __future__ import annotations
import logging
import threading
import time
from datetime import datetime, timedelta

import httpx

from database import db

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 300  # 5 minutes


class BackendSyncClient:
    def __init__(self, backend_url: str, api_key: str):
        self._backend_url = backend_url.rstrip("/")
        self._api_key = api_key
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_sync: dict[str, str] = {}  # table → last synced timestamp
        self._client = httpx.Client(
            base_url=self._backend_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=15.0,
        )

    def start(self) -> None:
        if not self._backend_url or not self._api_key:
            logger.info("Backend sync disabled (no FRIDAY_BACKEND_URL or key)")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="backend-sync"
        )
        self._thread.start()
        logger.info("Backend sync started → %s (every %ds)", self._backend_url, SYNC_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._running = False
        self._client.close()

    def sync_now(self) -> dict:
        """Force an immediate sync and return results."""
        return self._do_sync()

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        time.sleep(30)  # Initial delay — let runtime fully start first
        while self._running:
            try:
                results = self._do_sync()
                total = sum(r.get("synced", 0) for r in results.values())
                if total > 0:
                    logger.info("Backend sync: %d records pushed", total)
            except Exception as exc:
                logger.warning("Backend sync failed: %s", exc)
            time.sleep(SYNC_INTERVAL_SECONDS)

    def _do_sync(self) -> dict:
        results = {}
        for table, query, last_key in [
            ("interaction_events",
             "SELECT id, session_id, transcript, audio_hash, confidence, tool_called, tool_args, spoken_response, outcome, error, duration_ms, timestamp FROM interaction_events WHERE timestamp > ? ORDER BY timestamp LIMIT 200",
             "interaction_events"),
            ("correction_logs",
             "SELECT id, audio_hash, bad_transcript, corrected_text, timestamp FROM correction_logs WHERE timestamp > ? LIMIT 100",
             "correction_logs"),
            ("learned_aliases",
             "SELECT phrase, resolved_path, confidence, use_count, last_used FROM learned_aliases WHERE last_used > ? LIMIT 100",
             "learned_aliases"),
            ("reminders",
             "SELECT id, text, raw_input, due_at, place, category, status, follow_up_action, created_at FROM reminders WHERE updated_at > ? LIMIT 50",
             "reminders"),
            ("shopping_items",
             "SELECT id, item, store, quantity, checked, added_at FROM shopping_items WHERE added_at > ? LIMIT 50",
             "shopping_items"),
        ]:
            since = self._last_sync.get(last_key, "1970-01-01T00:00:00")
            rows = db.fetchall(query, (since,))
            if not rows:
                continue

            records = [dict(r) for r in rows]
            try:
                resp = self._client.post(
                    "/sync/batch",
                    json={"table": table, "records": records},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results[table] = data
                    # Advance last sync cursor to now
                    self._last_sync[last_key] = datetime.now().isoformat()
                else:
                    logger.warning("Sync %s returned %d", table, resp.status_code)
                    results[table] = {"error": resp.text[:100]}
            except Exception as exc:
                logger.debug("Sync %s error: %s", table, exc)
                results[table] = {"error": str(exc)}

        return results

    def check_health(self) -> bool:
        try:
            resp = self._client.get("/health", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False
