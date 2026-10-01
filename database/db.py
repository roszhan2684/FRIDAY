"""SQLite connection management and schema initialization."""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(os.path.expanduser("~/.friday/friday.db"))
MIGRATION_DIR = Path(__file__).parent / "migrations"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Run all migrations in order. Idempotent."""
    conn = get_connection()
    migration_files = sorted(MIGRATION_DIR.glob("*.sql"))
    for mf in migration_files:
        sql = mf.read_text()
        conn.executescript(sql)
    conn.commit()
    conn.close()


def fetchone(query: str, params: tuple = ()) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        return conn.execute(query, params).fetchone()
    finally:
        conn.close()


def fetchall(query: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def execute(query: str, params: tuple = ()) -> None:
    conn = get_connection()
    try:
        conn.execute(query, params)
        conn.commit()
    finally:
        conn.close()


def executemany(query: str, params_list: list[tuple]) -> None:
    conn = get_connection()
    try:
        conn.executemany(query, params_list)
        conn.commit()
    finally:
        conn.close()
