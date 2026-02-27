"""
fastcode.db — SQLite database initialisation.

Creates the chunks, sources, and chunks_fts tables used by the indexer
(Phase 12) and BM25 retriever (Phase 13).
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS sources (
    path         TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    mtime_ns     INTEGER NOT NULL,
    size         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path  TEXT NOT NULL REFERENCES sources(path) ON DELETE CASCADE,
    content      TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    chunk_index  INTEGER NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset   INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    content=chunks,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS chunks_ai
AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad
AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au
AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
END;
"""


def init_db(db_path: str) -> sqlite3.Connection:
    """
    Open (or create) the SQLite database at db_path and ensure all
    schema objects exist. Safe to call multiple times (idempotent).

    Args:
        db_path: Filesystem path to the SQLite database file.
                 Use ":memory:" for in-memory databases (tests).

    Returns:
        An open sqlite3.Connection with foreign keys enabled.
    """
    conn = sqlite3.connect(db_path)
    conn.executescript(_DDL)
    conn.execute("PRAGMA foreign_keys = ON")
    logger.info(f"Database initialised at {db_path}")
    return conn
