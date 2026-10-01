"""Phase 5 — Habit Detector.

Analyzes interaction history to detect:
  1. Time-based habits (e.g. "opens YouTube at 9 PM most days")
  2. Sequential habits (e.g. "always opens Terminal after VS Code")
  3. Daily routines (e.g. "morning mode every weekday before 9 AM")
  4. Errand patterns (e.g. "Target every Sunday")

Surfaces suggestions via routine_suggestions table.
Does NOT auto-execute anything — only surfaces for user confirmation.
"""
from __future__ import annotations
import json
import logging
import uuid
from collections import Counter, defaultdict
from datetime import datetime

from database import db

logger = logging.getLogger(__name__)

MIN_OCCURRENCES = 3          # Minimum times a pattern must appear to suggest
MIN_DAYS_OF_DATA = 3         # Don't suggest until we have at least 3 days of data


# ─── Time habit detection ─────────────────────────────────────────────────────

def detect_time_habits() -> list[dict]:
    """
    Find commands run at consistent times of day.
    Returns list of {tool, args, hour_bucket, day_pattern, count}.
    """
    rows = db.fetchall(
        """SELECT tool_called, tool_args,
                  CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                  strftime('%w', timestamp) as weekday
           FROM interaction_events
           WHERE tool_called IS NOT NULL
             AND outcome = 'success'
             AND timestamp >= datetime('now', '-30 days')
           ORDER BY timestamp DESC
           LIMIT 500"""
    )

    # Group by (tool, hour_bucket, weekday)
    pattern_counts: Counter = Counter()
    pattern_args: dict = {}

    for row in rows:
        tool = row["tool_called"]
        hour = row["hour"]
        weekday = row["weekday"]
        hour_bucket = (hour // 2) * 2  # 2-hour buckets: 0,2,4,6,...,22

        key = (tool, hour_bucket, weekday)
        pattern_counts[key] += 1
        if key not in pattern_args:
            try:
                pattern_args[key] = json.loads(row["tool_args"] or "{}")
            except Exception:
                pattern_args[key] = {}

    habits = []
    for (tool, hour_bucket, weekday), count in pattern_counts.items():
        if count >= MIN_OCCURRENCES:
            habits.append({
                "tool": tool,
                "args": pattern_args.get((tool, hour_bucket, weekday), {}),
                "hour_bucket": hour_bucket,
                "weekday": int(weekday),
                "count": count,
            })

    return sorted(habits, key=lambda x: -x["count"])


# ─── Sequential habit detection ───────────────────────────────────────────────

def detect_sequential_habits() -> list[dict]:
    """
    Find pairs of tools that are run in sequence within 5 minutes.
    Returns list of {first_tool, second_tool, count}.
    """
    rows = db.fetchall(
        """SELECT tool_called, timestamp
           FROM interaction_events
           WHERE tool_called IS NOT NULL AND outcome='success'
             AND timestamp >= datetime('now', '-30 days')
           ORDER BY timestamp ASC
           LIMIT 500"""
    )

    if len(rows) < 2:
        return []

    pair_counts: Counter = Counter()
    for i in range(len(rows) - 1):
        curr = rows[i]
        nxt = rows[i + 1]
        try:
            t1 = datetime.fromisoformat(curr["timestamp"])
            t2 = datetime.fromisoformat(nxt["timestamp"])
            gap_seconds = (t2 - t1).total_seconds()
            if 0 < gap_seconds <= 300:  # Within 5 minutes
                pair = (curr["tool_called"], nxt["tool_called"])
                if pair[0] != pair[1]:
                    pair_counts[pair] += 1
        except Exception:
            continue

    return [
        {"first_tool": pair[0], "second_tool": pair[1], "count": count}
        for pair, count in pair_counts.most_common(10)
        if count >= MIN_OCCURRENCES
    ]


# ─── Routine suggestion engine ────────────────────────────────────────────────

def suggest_new_routines() -> int:
    """
    Run all habit detectors and save new routine suggestions to DB.
    Returns number of new suggestions created.
    """
    days_of_data = _count_days_of_data()
    if days_of_data < MIN_DAYS_OF_DATA:
        logger.debug("Not enough data for habit detection (%d days)", days_of_data)
        return 0

    created = 0

    # Sequential pair suggestions
    for seq in detect_sequential_habits():
        if seq["count"] < MIN_OCCURRENCES:
            continue
        name = f"Auto: {seq['first_tool']} → {seq['second_tool']}"
        existing = db.fetchone(
            "SELECT id FROM routine_suggestions WHERE name=?", (name,)
        )
        if not existing:
            db.execute(
                "INSERT INTO routine_suggestions(id, name, steps, trigger_count) VALUES(?,?,?,?)",
                (str(uuid.uuid4()), name,
                 json.dumps([{"tool": seq["first_tool"]}, {"tool": seq["second_tool"]}]),
                 seq["count"]),
            )
            logger.info("Routine suggestion: %s (seen %d times)", name, seq["count"])
            created += 1
        else:
            db.execute(
                "UPDATE routine_suggestions SET trigger_count=? WHERE id=?",
                (seq["count"], existing["id"]),
            )

    return created


def _count_days_of_data() -> int:
    row = db.fetchone(
        "SELECT COUNT(DISTINCT DATE(timestamp)) as days FROM interaction_events"
    )
    return row["days"] if row else 0


# ─── Personalization context ──────────────────────────────────────────────────

def get_personalization_context() -> dict:
    """
    Return a summary of detected habits for injection into the planner.
    Kept small to avoid prompt bloat (< 200 tokens when serialized).
    """
    sequential = detect_sequential_habits()[:3]
    top_tools = _get_top_tools(5)
    return {
        "top_tools": top_tools,
        "sequential_patterns": [
            f"{s['first_tool']}→{s['second_tool']}" for s in sequential
        ],
    }


def _get_top_tools(limit: int = 5) -> list[str]:
    rows = db.fetchall(
        """SELECT tool_called, COUNT(*) as c
           FROM interaction_events
           WHERE tool_called IS NOT NULL AND outcome='success'
             AND timestamp >= datetime('now', '-7 days')
           GROUP BY tool_called
           ORDER BY c DESC
           LIMIT ?""",
        (limit,),
    )
    return [r["tool_called"] for r in rows]
