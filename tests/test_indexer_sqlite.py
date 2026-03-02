"""
Tests for fastcode.indexer.index_repo() — IDX-01 and IDX-02.
"""
import os
import sqlite3
import hashlib

import pytest

from fastcode.indexer import index_repo


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _py_file_content():
    return (
        "def hello():\n"
        "    return 'hello'\n"
        "\n"
        "def world():\n"
        "    return 'world'\n"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_directory(tmp_path):
    """Indexing an empty directory returns all-zero stats."""
    db_path = tmp_path / "test.db"
    stats = index_repo(str(tmp_path), str(db_path))
    assert stats == {"indexed": 0, "skipped": 0, "deleted": 0, "errors": 0}


def test_indexes_python_file(tmp_path):
    """Indexing a dir with one Python file → indexed==1, chunks table non-empty."""
    (tmp_path / "foo.py").write_text(_py_file_content())
    db_path = tmp_path / "test.db"
    stats = index_repo(str(tmp_path), str(db_path))
    assert stats["indexed"] == 1
    assert stats["errors"] == 0
    conn = _connect(db_path)
    rows = conn.execute("SELECT content FROM chunks").fetchall()
    assert len(rows) >= 1
    for (content,) in rows:
        assert content.strip() != ""
    conn.close()


def test_sources_table_populated(tmp_path):
    """After indexing, sources has one row with correct metadata."""
    (tmp_path / "foo.py").write_text(_py_file_content())
    db_path = tmp_path / "test.db"
    index_repo(str(tmp_path), str(db_path))
    conn = _connect(db_path)
    rows = conn.execute("SELECT path, content_hash, mtime_ns, size FROM sources").fetchall()
    assert len(rows) == 1
    path, content_hash, mtime_ns, size = rows[0]
    assert path == "foo.py"
    assert len(content_hash) == 64  # SHA-256 hex
    assert mtime_ns > 0
    assert size > 0
    conn.close()


def test_reindex_unchanged_skips(tmp_path):
    """Re-indexing an unchanged file → skipped==1, indexed==0, chunk count unchanged."""
    (tmp_path / "foo.py").write_text(_py_file_content())
    db_path = tmp_path / "test.db"
    index_repo(str(tmp_path), str(db_path))
    conn = _connect(db_path)
    first_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()

    stats2 = index_repo(str(tmp_path), str(db_path))
    assert stats2["skipped"] == 1
    assert stats2["indexed"] == 0

    conn = _connect(db_path)
    second_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    assert second_count == first_count


def test_reindex_modified_rerenders(tmp_path):
    """Re-indexing after file content changes → indexed==1, chunk count changes."""
    py_file = tmp_path / "foo.py"
    py_file.write_text(_py_file_content())
    db_path = tmp_path / "test.db"
    index_repo(str(tmp_path), str(db_path))
    conn = _connect(db_path)
    first_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()

    # Overwrite with different content (extra function)
    py_file.write_text(
        _py_file_content()
        + "\ndef extra():\n    return 'extra'\n"
    )
    stats2 = index_repo(str(tmp_path), str(db_path))
    assert stats2["indexed"] == 1
    assert stats2["skipped"] == 0

    conn = _connect(db_path)
    second_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    # More functions → more chunks (or at least equal; ensure we actually re-indexed)
    assert second_count >= first_count


def test_deleted_file_removed(tmp_path):
    """After deleting a file, re-index produces deleted==1 and empty tables."""
    py_file = tmp_path / "foo.py"
    py_file.write_text(_py_file_content())
    db_path = tmp_path / "test.db"
    index_repo(str(tmp_path), str(db_path))

    py_file.unlink()
    stats2 = index_repo(str(tmp_path), str(db_path))
    assert stats2["deleted"] == 1

    conn = _connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
    conn.close()


def test_gitignore_respected(tmp_path):
    """.gitignore patterns exclude matched files."""
    (tmp_path / ".gitignore").write_text("*.log\n")
    (tmp_path / "keep.py").write_text(_py_file_content())
    (tmp_path / "ignore.log").write_text("some log content\n")
    db_path = tmp_path / "test.db"
    stats = index_repo(str(tmp_path), str(db_path))

    conn = _connect(db_path)
    paths = {row[0] for row in conn.execute("SELECT path FROM sources").fetchall()}
    conn.close()

    assert "ignore.log" not in paths
    # The .py file is indexed
    assert stats["indexed"] == 1


def test_hidden_dir_skipped(tmp_path):
    """Files inside hidden directories are not indexed."""
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.py").write_text(_py_file_content())
    db_path = tmp_path / "test.db"
    stats = index_repo(str(tmp_path), str(db_path))

    conn = _connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    conn.close()

    assert count == 0
    assert stats["indexed"] == 0
