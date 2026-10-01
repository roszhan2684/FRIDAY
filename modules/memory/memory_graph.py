"""Phase 5 — Memory Graph.

Extracts and stores a lightweight personal knowledge graph from interactions:
  - People ("call mom", "meeting with Sarah")
  - Places ("Target", "gym", "office")
  - Files ("my resume", "the pitch deck")
  - Sites ("LinkedIn", "GitHub", "Jobright")
  - Routines patterns

Stored in memory_nodes + memory_edges (SQLite, syncs to backend Postgres).
Used by the planner to enrich context and by the briefing to personalize responses.
"""
from __future__ import annotations
import json
import logging
import re
import uuid
from datetime import datetime

from database import db

logger = logging.getLogger(__name__)

# ─── Entity extraction patterns ───────────────────────────────────────────────

PERSON_PATTERNS = [
    r"call\s+(\w+)",
    r"text\s+(\w+)",
    r"meeting with\s+([\w\s]+?)(?:\s+at|\s+on|$)",
    r"email\s+(\w+)",
    r"remind\s+me\s+to\s+(?:call|text|email)\s+(\w+)",
]

PLACE_PATTERNS = [
    r"(?:go to|at|from)\s+(Target|Walmart|Costco|Trader Joe['s]*|CVS|Walgreens|Starbucks|gym|office|home|school|class)",
    r"open (?:Maps|Apple Maps|Google Maps) (?:for|to)\s+([\w\s]+)",
]

SITE_PATTERNS = [
    r"open\s+(LinkedIn|GitHub|Glassdoor|JobRight|Netflix|YouTube|Gmail|Notion)",
    r"go to\s+([\w]+\.(?:com|ai|io|org))",
]


def extract_entities(text: str) -> list[dict]:
    """Extract named entities from a transcript."""
    t = text.lower()
    entities = []

    for pattern in PERSON_PATTERNS:
        for m in re.finditer(pattern, t, re.I):
            name = m.group(1).strip().title()
            if len(name) > 1 and name.lower() not in ("me", "my", "the", "a"):
                entities.append({"type": "person", "label": name})

    for pattern in PLACE_PATTERNS:
        for m in re.finditer(pattern, t, re.I):
            place = m.group(1).strip().title()
            entities.append({"type": "place", "label": place})

    for pattern in SITE_PATTERNS:
        for m in re.finditer(pattern, t, re.I):
            site = m.group(1).strip()
            entities.append({"type": "site", "label": site})

    return entities


# ─── Graph operations ─────────────────────────────────────────────────────────

def upsert_node(node_type: str, label: str, attributes: dict | None = None) -> str:
    """Create or update a memory node. Returns node id."""
    label_lower = label.lower().strip()
    existing = db.fetchone(
        "SELECT id, mention_count FROM memory_nodes WHERE LOWER(label)=? AND node_type=?",
        (label_lower, node_type),
    )
    if existing:
        db.execute(
            "UPDATE memory_nodes SET mention_count=mention_count+1, last_mentioned=datetime('now') WHERE id=?",
            (existing["id"],),
        )
        return existing["id"]

    node_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO memory_nodes(id, node_type, label, attributes, mention_count) VALUES(?,?,?,?,1)",
        (node_id, node_type, label, json.dumps(attributes or {})),
    )
    return node_id


def add_edge(source_id: str, target_id: str, relation: str, weight: float = 1.0) -> None:
    """Add or reinforce an edge between two nodes."""
    existing = db.fetchone(
        "SELECT id, weight FROM memory_edges WHERE source_id=? AND target_id=? AND relation=?",
        (source_id, target_id, relation),
    )
    if existing:
        db.execute(
            "UPDATE memory_edges SET weight=weight+? WHERE id=?",
            (weight * 0.1, existing["id"]),
        )
    else:
        db.execute(
            "INSERT INTO memory_edges(source_id, target_id, relation, weight) VALUES(?,?,?,?)",
            (source_id, target_id, relation, weight),
        )


def get_related_nodes(label: str, relation: str | None = None, limit: int = 5) -> list[dict]:
    """Find nodes related to a given label."""
    node = db.fetchone(
        "SELECT id FROM memory_nodes WHERE LOWER(label)=?", (label.lower(),)
    )
    if not node:
        return []
    q = ("SELECT n.label, n.node_type, e.relation, e.weight "
         "FROM memory_edges e JOIN memory_nodes n ON e.target_id=n.id "
         "WHERE e.source_id=?")
    params: tuple = (node["id"],)
    if relation:
        q += " AND e.relation=?"
        params = (node["id"], relation)
    q += " ORDER BY e.weight DESC LIMIT ?"
    params = (*params, limit)
    return [dict(r) for r in db.fetchall(q, params)]


def process_interaction(transcript: str, tool_called: str, tool_args: dict) -> None:
    """
    Called after every successful interaction to update the memory graph.
    Extracts entities and records the action taken with those entities.
    """
    entities = extract_entities(transcript)
    if not entities:
        return

    for entity in entities:
        node_id = upsert_node(entity["type"], entity["label"])

        # Record relationship between entity and action taken
        action_node_id = upsert_node("action", tool_called)
        add_edge(node_id, action_node_id, "used_with", weight=1.0)

        # Special relationships
        if tool_called == "create_reminder" and entity["type"] == "place":
            errand_node_id = upsert_node("action", "errand")
            add_edge(node_id, errand_node_id, "errand_location", weight=1.5)

    logger.debug("Memory graph updated: %d entities from %r", len(entities), transcript[:60])


def get_frequent_people(limit: int = 5) -> list[str]:
    rows = db.fetchall(
        "SELECT label FROM memory_nodes WHERE node_type='person' ORDER BY mention_count DESC LIMIT ?",
        (limit,),
    )
    return [r["label"] for r in rows]


def get_frequent_places(limit: int = 5) -> list[str]:
    rows = db.fetchall(
        "SELECT label FROM memory_nodes WHERE node_type='place' ORDER BY mention_count DESC LIMIT ?",
        (limit,),
    )
    return [r["label"] for r in rows]


def get_graph_summary() -> dict:
    """Return a summary of the memory graph for use in briefings/context."""
    counts = {}
    for node_type in ("person", "place", "site", "file", "action"):
        row = db.fetchone(
            "SELECT COUNT(*) as c FROM memory_nodes WHERE node_type=?", (node_type,)
        )
        counts[node_type] = row["c"] if row else 0
    return {
        "total_nodes": sum(counts.values()),
        "by_type": counts,
        "frequent_people": get_frequent_people(3),
        "frequent_places": get_frequent_places(3),
    }
