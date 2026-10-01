"""File search using macOS Spotlight (mdfind) + learned alias table.

Resolution order:
  1. Exact alias match in learned_aliases DB
  2. Spotlight search with alias as query
  3. Spotlight search with original query
  4. Recent files Spotlight fallback
"""
from __future__ import annotations
import logging
import subprocess
from pathlib import Path

from database import db

logger = logging.getLogger(__name__)

SPOTLIGHT_TIMEOUT = 5.0


def resolve_file(query: str, hint: str = "") -> str | None:
    """
    Find the most likely file path for a natural language query.
    Returns the best match path or None.
    """
    # 1. Check learned aliases
    alias_path = _lookup_alias(query)
    if alias_path and Path(alias_path).exists():
        logger.info("Alias hit: %r → %s", query, alias_path)
        return alias_path

    # 2. Spotlight search
    search_query = f"{query} {hint}".strip()
    results = spotlight_search(search_query, limit=5)
    if results:
        best = _rank_results(results, query, hint)
        logger.info("Spotlight hit: %r → %s", query, best)
        return best

    logger.warning("No file found for query: %r", query)
    return None


def spotlight_search(query: str, limit: int = 10, kind: str = "") -> list[str]:
    """
    Run mdfind with optional kind filter.
    kind examples: 'pdf', 'docx', 'folder', 'image'
    """
    cmd = ["mdfind", "-onlyin", str(Path.home()), query]

    if kind:
        # Add kind predicate for common types
        kind_map = {
            "pdf": "kMDItemContentType == 'com.adobe.pdf'",
            "folder": "kMDItemContentType == 'public.folder'",
            "image": "kMDItemContentTypeTree == 'public.image'",
            "doc": "kMDItemContentType == 'com.microsoft.word.doc'",
            "docx": "kMDItemContentType == 'org.openxmlformats.wordprocessingml.document'",
        }
        if kind in kind_map:
            cmd = ["mdfind", kind_map[kind], "-onlyin", str(Path.home())]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SPOTLIGHT_TIMEOUT,
        )
        paths = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        return paths[:limit]
    except subprocess.TimeoutExpired:
        logger.warning("Spotlight timed out for query: %r", query)
        return []
    except Exception as exc:
        logger.error("Spotlight error: %s", exc)
        return []


def recent_files(limit: int = 20) -> list[str]:
    """Get recently accessed files via Spotlight."""
    return spotlight_search("", limit=limit)


def _lookup_alias(phrase: str) -> str | None:
    phrase_lower = phrase.lower().strip()
    row = db.fetchone(
        "SELECT resolved_path FROM learned_aliases WHERE LOWER(phrase) = ? ORDER BY confidence DESC, use_count DESC LIMIT 1",
        (phrase_lower,),
    )
    return row["resolved_path"] if row else None


def _rank_results(paths: list[str], query: str, hint: str) -> str:
    """
    Score results and return the best match.
    Scoring: filename match > recency > file type hint match.
    """
    query_lower = query.lower()
    hint_lower = hint.lower()

    def score(path: str) -> float:
        p = Path(path)
        name = p.stem.lower()
        suffix = p.suffix.lower().lstrip(".")
        s = 0.0

        # Filename contains query words
        for word in query_lower.split():
            if word in name:
                s += 1.0

        # Hint matches file type
        if hint_lower and hint_lower in suffix:
            s += 0.5

        # Prefer non-hidden, non-system paths
        if "Library" not in path and "/." not in path:
            s += 0.3

        # Prefer shorter paths (more likely to be user-facing)
        s -= len(path) * 0.001

        return s

    return max(paths, key=score)


def register_alias(phrase: str, resolved_path: str) -> None:
    """Save or update a learned alias."""
    db.execute(
        """
        INSERT INTO learned_aliases(phrase, resolved_path, use_count, last_used)
        VALUES (?, ?, 1, datetime('now'))
        ON CONFLICT(phrase) DO UPDATE SET
            resolved_path = excluded.resolved_path,
            use_count = use_count + 1,
            last_used = datetime('now')
        """,
        (phrase.lower().strip(), resolved_path),
    )


def increment_alias_use(phrase: str) -> None:
    db.execute(
        "UPDATE learned_aliases SET use_count = use_count + 1, last_used = datetime('now') WHERE LOWER(phrase) = ?",
        (phrase.lower().strip(),),
    )
