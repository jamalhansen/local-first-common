import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

def _resolve_quality_db_path() -> Path:
    """Resolve the content quality database path with fallback logic."""
    # 1. Environment variable override
    if env := os.environ.get("LOCAL_FIRST_QUALITY_DB"):
        return Path(env).expanduser()
    
    # 2. Preferred sync path
    sync_path = Path("~/sync/local-first/content_quality.db").expanduser()
    if sync_path.exists():
        return sync_path
    
    # 3. Local fallback (XDG-ish)
    fallback_path = Path("~/.local/share/local-first/content_quality.db").expanduser()
    return fallback_path

# Standard paths for syncing across devices
CONTENT_QUALITY_DB_PATH = _resolve_quality_db_path()


@contextmanager
def get_db_cursor(db_path: str | Path) -> Generator[Optional[sqlite3.Cursor], None, None]:
    """Context manager for a SQLite database cursor.
    
    Handles connection, sets Row factory, and closes on exit.
    Yields None if the database file does not exist.
    """
    path = Path(db_path).expanduser()
    if not path.exists():
        yield None
        return
    
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn.cursor()
    finally:
        conn.close()

def init_db(db_path: str | Path, schema_sql: str) -> None:
    """Initialize a SQLite database with the given schema if it doesn't exist."""
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

def is_seen(db_path: str | Path, table: str, url_col: str, url: str) -> bool:
    """Check if a URL already exists in the given table."""
    with get_db_cursor(db_path) as cur:
        if cur is None:
            return False
        cur.execute(f"SELECT 1 FROM {table} WHERE {url_col} = ?", (url,))
        return cur.fetchone() is not None

def mark_status(
    db_path: str | Path,
    table: str,
    url_col: str,
    url: str,
    status_col: str,
    status: str,
    timestamp_col: str | None = None,
) -> None:
    """Update the status of an item by its URL."""
    path = Path(db_path).expanduser()
    if not path.exists():
        # Auto-create directory if it doesn't exist when we are about to write
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        if timestamp_col:
            from datetime import datetime
            now = datetime.now().isoformat()
            conn.execute(
                f"UPDATE {table} SET {status_col} = ?, {timestamp_col} = ? WHERE {url_col} = ?",
                (status, now, url),
            )
        else:
            conn.execute(
                f"UPDATE {table} SET {status_col} = ? WHERE {url_col} = ?",
                (status, url),
            )
        conn.commit()
    finally:
        conn.close()
