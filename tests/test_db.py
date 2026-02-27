"""
Tests for fastcode.db — SQLite schema initialisation.
"""
import tempfile
import os

import pytest

from fastcode.db import init_db


def test_chunks_table_columns():
    conn = init_db(":memory:")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(chunks)").fetchall()}
    assert cols == {"id", "source_path", "content", "content_hash", "chunk_index", "start_offset", "end_offset"}


def test_sources_table_columns():
    conn = init_db(":memory:")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(sources)").fetchall()}
    assert cols == {"path", "content_hash", "mtime_ns", "size"}


def test_chunks_fts_virtual_table_exists():
    conn = init_db(":memory:")
    row = conn.execute(
        "SELECT type FROM sqlite_master WHERE name='chunks_fts'"
    ).fetchone()
    assert row is not None
    assert row[0] == "table"


def test_fts_trigger_insert():
    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO sources(path, content_hash, mtime_ns, size) VALUES (?,?,?,?)",
        ("/repo/foo.py", "abc123", 1_000_000, 512),
    )
    conn.execute(
        "INSERT INTO chunks(source_path, content, content_hash, chunk_index, start_offset, end_offset) "
        "VALUES (?,?,?,?,?,?)",
        ("/repo/foo.py", "def hello_world(): pass", "def123", 0, 0, 22),
    )
    conn.commit()
    results = conn.execute(
        "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'hello_world'"
    ).fetchall()
    assert len(results) == 1, "FTS trigger did not index the inserted chunk"


def test_fts_trigger_delete():
    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO sources(path, content_hash, mtime_ns, size) VALUES (?,?,?,?)",
        ("/repo/bar.py", "abc123", 1_000_000, 512),
    )
    conn.execute(
        "INSERT INTO chunks(source_path, content, content_hash, chunk_index, start_offset, end_offset) "
        "VALUES (?,?,?,?,?,?)",
        ("/repo/bar.py", "def goodbye_world(): pass", "gbye123", 0, 0, 25),
    )
    conn.commit()
    chunk_id = conn.execute("SELECT id FROM chunks WHERE source_path='/repo/bar.py'").fetchone()[0]
    conn.execute("DELETE FROM chunks WHERE id=?", (chunk_id,))
    conn.commit()
    results = conn.execute(
        "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'goodbye_world'"
    ).fetchall()
    assert len(results) == 0, "FTS trigger did not remove the deleted chunk"


def test_init_db_idempotent():
    conn = init_db(":memory:")
    # Second call on same connection path must not raise
    conn2 = init_db(":memory:")
    # Each in-memory DB is independent; verify schema still present
    cols = {row[1] for row in conn2.execute("PRAGMA table_info(chunks)").fetchall()}
    assert "id" in cols


def test_init_db_idempotent_file(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn1 = init_db(db_path)
    conn1.close()
    # Second init on same file must not raise
    conn2 = init_db(db_path)
    cols = {row[1] for row in conn2.execute("PRAGMA table_info(chunks)").fetchall()}
    assert "id" in cols
    conn2.close()
