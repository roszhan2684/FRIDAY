"""Learning pipeline — updates memory based on interaction outcomes.

Called after every interaction. Handles:
  - Alias reinforcement from successful file opens
  - Correction ingestion from typed fixes
  - Routine suggestion from repeated command sequences
  - Confidence decay for aliases pointing to deleted files
"""
from __future__ import annotations
import json
import logging
from collections import Counter
from pathlib import Path

from modules.memory.store import (
    upsert_alias,
    get_all_aliases,
    log_correction,
    get_recent_transcripts,
)
from database import db
from shared.schemas import InteractionEvent, CorrectionEvent, OutcomeStatus

logger = logging.getLogger(__name__)

ROUTINE_SUGGEST_THRESHOLD = 3   # Suggest routine after seeing same sequence N times
ALIAS_DECAY_THRESHOLD = 0.3     # Remove alias if confidence drops below this


class Learner:

    def update_from_interaction(self, event: InteractionEvent) -> None:
        """Process an interaction event and update relevant memory."""
        if event.tool_called == "open_file" and event.outcome == OutcomeStatus.SUCCESS:
            self._learn_file_alias(event)

        if event.outcome == OutcomeStatus.CORRECTED:
            self._handle_correction_outcome(event)

        self._check_routine_patterns()

        # Phase 5: update memory graph + run habit detection periodically
        if event.outcome == OutcomeStatus.SUCCESS:
            try:
                from modules.memory.memory_graph import process_interaction
                process_interaction(event.transcript, event.tool_called or "", event.tool_args)
            except Exception as exc:
                logger.debug("Memory graph update failed: %s", exc)

        # Run habit detection every 20 interactions to avoid overhead
        try:
            row = db.fetchone("SELECT COUNT(*) as c FROM interaction_events")
            if row and row["c"] % 20 == 0:
                from modules.memory.habit_detector import suggest_new_routines
                new = suggest_new_routines()
                if new:
                    logger.info("Habit detector found %d new routine suggestions", new)
        except Exception as exc:
            logger.debug("Habit detection failed: %s", exc)

    def ingest_correction(self, audio_hash: str, bad: str, corrected: str) -> None:
        """Save a typed correction from the user."""
        evt = CorrectionEvent(
            audio_hash=audio_hash,
            bad_transcript=bad,
            corrected_text=corrected,
        )
        log_correction(evt)
        logger.info("Correction saved: %r → %r", bad, corrected)

    def validate_aliases(self) -> int:
        """
        Check all stored aliases point to existing files.
        Remove or decay confidence of stale aliases.
        Returns count of removed aliases.
        """
        aliases = get_all_aliases()
        removed = 0
        for phrase, path in aliases.items():
            if not Path(path).exists():
                row = db.fetchone("SELECT confidence, use_count FROM learned_aliases WHERE phrase = ?", (phrase,))
                if row:
                    new_confidence = row["confidence"] * 0.5
                    if new_confidence < ALIAS_DECAY_THRESHOLD:
                        db.execute("DELETE FROM learned_aliases WHERE phrase = ?", (phrase,))
                        logger.info("Removed stale alias: %r → %s", phrase, path)
                        removed += 1
                    else:
                        db.execute(
                            "UPDATE learned_aliases SET confidence = ? WHERE phrase = ?",
                            (new_confidence, phrase),
                        )
        return removed

    def _learn_file_alias(self, event: InteractionEvent) -> None:
        """When a file is successfully opened, reinforce the alias."""
        query = event.tool_args.get("query", "")
        # Path is stored in metadata by MacActionExecutor._tool_open_file
        path = event.metadata.get("path", "")
        if query and path:
            upsert_alias(query, path, confidence=1.0)
            logger.debug("Alias learned: %r → %s", query, path)

    def _handle_correction_outcome(self, event: InteractionEvent) -> None:
        logger.info("Interaction %s was corrected — flagging for review", event.id)

    def _check_routine_patterns(self) -> None:
        """
        Look for repeated N-grams in recent transcripts.
        If a sequence repeats >= ROUTINE_SUGGEST_THRESHOLD, propose a routine.
        """
        recent = get_recent_transcripts(limit=50)
        if len(recent) < ROUTINE_SUGGEST_THRESHOLD * 2:
            return

        # Build bigrams of (tool, tool) from recent interactions
        rows = db.fetchall(
            "SELECT tool_called FROM interaction_events WHERE tool_called IS NOT NULL ORDER BY timestamp DESC LIMIT 50"
        )
        tools = [r["tool_called"] for r in rows if r["tool_called"]]
        bigrams = Counter(zip(tools, tools[1:]))

        for (t1, t2), count in bigrams.items():
            if count >= ROUTINE_SUGGEST_THRESHOLD and t1 != t2:
                existing = db.fetchone(
                    "SELECT id FROM routine_suggestions WHERE steps LIKE ?",
                    (f"%{t1}%{t2}%",),
                )
                if not existing:
                    import uuid
                    db.execute(
                        "INSERT INTO routine_suggestions(id, name, steps, trigger_count) VALUES (?,?,?,?)",
                        (
                            str(uuid.uuid4()),
                            f"Auto: {t1} then {t2}",
                            json.dumps([{"tool": t1}, {"tool": t2}]),
                            count,
                        ),
                    )
                    logger.info("Routine suggestion created: %s → %s (seen %d times)", t1, t2, count)
