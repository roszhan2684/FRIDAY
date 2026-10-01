-- Migration 006 — Phase 6: Job Copilot + Second Brain

-- ─── Job Applications ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS job_applications (
    id          TEXT PRIMARY KEY,
    company     TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT '',
    url         TEXT DEFAULT '',
    status      TEXT DEFAULT 'applied',    -- applied|screening|interview|offer|rejected|withdrawn
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    notes       TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON job_applications(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON job_applications(LOWER(company));

-- ─── Second Brain (quick note capture) ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS second_brain (
    id          TEXT PRIMARY KEY,
    text        TEXT NOT NULL,
    category    TEXT DEFAULT 'general',    -- general|idea|todo|meeting|learning
    tags        TEXT DEFAULT '[]',         -- JSON array
    pinned      INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_brain_category ON second_brain(category);
CREATE INDEX IF NOT EXISTS idx_brain_created ON second_brain(created_at);

-- ─── Memory nodes/edges (Phase 5 — if migration 005 ran, these are added) ───

CREATE TABLE IF NOT EXISTS memory_nodes (
    id              TEXT PRIMARY KEY,
    node_type       TEXT NOT NULL,
    label           TEXT NOT NULL,
    attributes      TEXT DEFAULT '{}',
    mention_count   INTEGER DEFAULT 1,
    last_mentioned  TEXT NOT NULL DEFAULT (datetime('now')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_mem_nodes_type ON memory_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_mem_nodes_label ON memory_nodes(LOWER(label));

CREATE TABLE IF NOT EXISTS memory_edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT NOT NULL REFERENCES memory_nodes(id) ON DELETE CASCADE,
    target_id   TEXT NOT NULL REFERENCES memory_nodes(id) ON DELETE CASCADE,
    relation    TEXT NOT NULL,
    weight      REAL DEFAULT 1.0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── Preferences for Phase 6 ─────────────────────────────────────────────────

INSERT OR IGNORE INTO preferences(key, value) VALUES
    ('quiet_hours_start', '22'),
    ('quiet_hours_end', '8'),
    ('daily_reflection_enabled', 'true'),
    ('second_brain_enabled', 'true');
