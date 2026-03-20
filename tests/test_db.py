"""Tests for db.py — SQLite utilities for local-first tools."""

import sqlite3
from local_first_common import db


def test_init_db(tmp_path):
    """Initializes a new DB with schema."""
    db_path = tmp_path / "test.db"
    schema = "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);"
    db.init_db(db_path, schema)
    
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    assert cur.fetchone() is not None
    conn.close()


def test_get_db_cursor_exists(tmp_path):
    """Yields a working cursor if DB exists."""
    db_path = tmp_path / "test.db"
    db.init_db(db_path, "CREATE TABLE t (id INTEGER);")
    
    with db.get_db_cursor(db_path) as cur:
        assert cur is not None
        cur.execute("INSERT INTO t VALUES (1);")
        cur.connection.commit()
    
    # Verify write
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 1
    conn.close()


def test_get_db_cursor_not_found(tmp_path):
    """Yields None if DB does not exist."""
    db_path = tmp_path / "nonexistent.db"
    with db.get_db_cursor(db_path) as cur:
        assert cur is None


def test_is_seen(tmp_path):
    """Correctly detects presence/absence of URL."""
    db_path = tmp_path / "test.db"
    db.init_db(db_path, "CREATE TABLE links (url TEXT PRIMARY KEY);")
    
    assert not db.is_seen(db_path, "links", "url", "https://example.com")
    
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO links (url) VALUES (?)", ("https://example.com",))
    conn.commit()
    conn.close()
    
    assert db.is_seen(db_path, "links", "url", "https://example.com")


def test_mark_status(tmp_path):
    """Updates status and optional timestamp."""
    db_path = tmp_path / "test.db"
    db.init_db(db_path, "CREATE TABLE items (url TEXT PRIMARY KEY, status TEXT, updated_at TEXT);")
    
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO items (url, status) VALUES (?, ?)", ("http://t.co", "new"))
    conn.commit()
    conn.close()
    
    db.mark_status(db_path, "items", "url", "http://t.co", "status", "read", "updated_at")
    
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status, updated_at FROM items").fetchone()
    assert row[0] == "read"
    assert row[1] is not None # timestamp set
    conn.close()


def test_mark_status_no_timestamp(tmp_path):
    """Updates status without timestamp."""
    db_path = tmp_path / "test.db"
    db.init_db(db_path, "CREATE TABLE items (url TEXT PRIMARY KEY, status TEXT);")
    
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO items (url, status) VALUES (?, ?)", ("http://t.co", "new"))
    conn.commit()
    conn.close()
    
    db.mark_status(db_path, "items", "url", "http://t.co", "status", "read")
    
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM items").fetchone()
    assert row[0] == "read"
    conn.close()
