"""Processing run tracker — logs tool/model/source/timing/item count to a central DuckDB file.

Each local-first tool calls ``log_run()`` after completing an LLM call.  The
function is fire-and-forget: it never raises, so a tracking failure never
breaks a tool.

Default DB path: ``~/sync/local-first/processing_log.duckdb``
Override:        ``LOCAL_FIRST_TRACKING_DB`` environment variable

Typical usage (LLM run context manager)::

    from local_first_common.tracking import timed_run

    with timed_run("my-tool", llm.model, source_location=url) as run:
        results = process_items(items)
        run.item_count = len(results)   # set at any point inside the block

Typical usage (URL fetch context manager)::

    from local_first_common.tracking import register_tool, tracked_fetch

    # Once at startup:
    tool = register_tool("my-tool")

    # Per fetch:
    with tracked_fetch(tool, url, source_url=post_url, source_platform="bluesky") as fetch:
        if fetch.html is None:
            return None          # failed — already logged
        metadata = parse(fetch.html)
        fetch.title = metadata.title
"""

import os
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

_DEFAULT_SYNC_PATH = Path("~/sync/local-first/processing_log.duckdb").expanduser()

# ── processing_log (LLM runs) ────────────────────────────────────────────────

_CREATE_SEQUENCE = "CREATE SEQUENCE IF NOT EXISTS processing_log_id_seq START 1;"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS processing_log (
    id               BIGINT  DEFAULT nextval('processing_log_id_seq') PRIMARY KEY,
    tool_name        VARCHAR NOT NULL,
    model            VARCHAR,
    source_location  VARCHAR,
    item_count       INTEGER,
    input_tokens     INTEGER,
    output_tokens    INTEGER,
    duration_seconds DOUBLE,
    success          BOOLEAN NOT NULL DEFAULT TRUE,
    error_message    VARCHAR,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_INSERT = """
INSERT INTO processing_log
    (tool_name, model, source_location, item_count, input_tokens, output_tokens,
     duration_seconds, success, error_message)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

# ── tools + fetch_log (URL fetches) ─────────────────────────────────────────

_CREATE_TOOLS_SEQUENCE = "CREATE SEQUENCE IF NOT EXISTS tools_id_seq START 1;"

_CREATE_TOOLS_TABLE = """
CREATE TABLE IF NOT EXISTS tools (
    id         BIGINT DEFAULT nextval('tools_id_seq') PRIMARY KEY,
    name       VARCHAR UNIQUE NOT NULL,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_FETCH_LOG_SEQUENCE = "CREATE SEQUENCE IF NOT EXISTS fetch_log_id_seq START 1;"

_CREATE_FETCH_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS fetch_log (
    id              BIGINT DEFAULT nextval('fetch_log_id_seq') PRIMARY KEY,
    tool_id         BIGINT REFERENCES tools(id),
    url             VARCHAR NOT NULL,
    domain          VARCHAR,
    source_url      VARCHAR,       -- social post or page where this link was found
    source_platform VARCHAR,       -- 'bluesky', 'mastodon', 'rss', etc.
    attempted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success         BOOLEAN NOT NULL,
    http_status     INTEGER,
    error_message   VARCHAR,
    duration_ms     INTEGER,
    title           VARCHAR        -- populated by caller after HTML parsing
);
"""

_UPSERT_TOOL = "INSERT INTO tools (name) VALUES (?) ON CONFLICT (name) DO NOTHING;"
_SELECT_TOOL_ID = "SELECT id FROM tools WHERE name = ?;"

_INSERT_FETCH = """
INSERT INTO fetch_log
    (tool_id, url, domain, source_url, source_platform,
     success, http_status, error_message, duration_ms, title)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def _resolve_db_path(override: str | Path | None = None) -> Path:
    """Return the DuckDB file path, creating parent directories as needed."""
    if override:
        path = Path(override).expanduser()
    elif env := os.environ.get("LOCAL_FIRST_TRACKING_DB"):
        path = Path(env).expanduser()
    else:
        path = _DEFAULT_SYNC_PATH

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_schema(conn) -> None:
    conn.execute(_CREATE_SEQUENCE)
    conn.execute(_CREATE_TABLE)
    conn.execute(_CREATE_TOOLS_SEQUENCE)
    conn.execute(_CREATE_TOOLS_TABLE)
    conn.execute(_CREATE_FETCH_LOG_SEQUENCE)
    conn.execute(_CREATE_FETCH_LOG_TABLE)


# ── LLM run tracking ─────────────────────────────────────────────────────────

def log_run(
    tool_name: str,
    model: str | None,
    *,
    source_location: str | None = None,
    item_count: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    duration_seconds: float | None = None,
    success: bool = True,
    error_message: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    """Insert one processing-run row.  Never raises — failures emit a warning."""
    # Coerce model to str or None — guards against MagicMock in tests
    if model is not None and not isinstance(model, str):
        model = str(model)
    try:
        import duckdb  # lazy import so tools without duckdb still load

        path = _resolve_db_path(db_path)
        conn = duckdb.connect(str(path))
        try:
            _ensure_schema(conn)
            conn.execute(
                _INSERT,
                [
                    tool_name,
                    model,
                    source_location,
                    item_count,
                    input_tokens,
                    output_tokens,
                    duration_seconds,
                    success,
                    error_message,
                ],
            )
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"[tracking] log_run failed: {exc}", stacklevel=2)


def timed_run(
    tool_name: str,
    model: str | None,
    source_location: str | None = None,
    db_path: str | Path | None = None,
) -> "_TimedRun":
    """Context manager that times a block and logs success/failure automatically.

    Set ``run.item_count`` inside the block to record how many items were processed::

        with timed_run("my-tool", llm.model, source_location=url) as run:
            results = process_batch(items)
            run.item_count = len(results)
    """
    return _TimedRun(tool_name, model, source_location, db_path)


class _TimedRun:
    def __init__(self, tool_name, model, source_location, db_path):
        self.tool_name = tool_name
        self.model = model
        self.source_location = source_location
        self.db_path = db_path
        self.item_count: int | None = None
        self._start: float = 0.0

    def __enter__(self) -> "_TimedRun":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, _tb):
        duration = time.monotonic() - self._start
        try:
            log_run(
                self.tool_name,
                self.model,
                source_location=self.source_location,
                item_count=self.item_count,
                duration_seconds=duration,
                success=exc_type is None,
                error_message=str(exc_val) if exc_val else None,
                db_path=self.db_path,
            )
        except Exception:  # noqa: BLE001
            pass  # log_run warnings-as-errors must not escape the context manager
        return False  # never suppress exceptions from the with-block body


# ── Tool registration + URL fetch tracking ───────────────────────────────────

@dataclass
class Tool:
    """A registered tool. Carries the DB id used in fetch_log rows.

    Obtain via ``register_tool()``. If registration failed (DB unavailable),
    ``id`` is None and fetch logging is silently skipped.
    """
    name: str
    id: int | None = field(default=None)


def register_tool(name: str, db_path: str | Path | None = None) -> "Tool":
    """Register a tool in the tools table and return a Tool object.

    Call once at tool startup — not per request. Never raises; returns a Tool
    with ``id=None`` if the DB is unavailable (fetch logging is then skipped).
    """
    try:
        import duckdb

        path = _resolve_db_path(db_path)
        conn = duckdb.connect(str(path))
        try:
            _ensure_schema(conn)
            conn.execute(_UPSERT_TOOL, [name])
            row = conn.execute(_SELECT_TOOL_ID, [name]).fetchone()
            tool_id = row[0] if row else None
        finally:
            conn.close()
        return Tool(name=name, id=tool_id)
    except Exception:  # noqa: BLE001
        return Tool(name=name, id=None)


def tracked_fetch(
    tool: "Tool",
    url: str,
    source_url: str | None = None,
    source_platform: str | None = None,
    db_path: str | Path | None = None,
) -> "_FetchContext":
    """Context manager that fetches a URL and logs the attempt to fetch_log.

    The fetch is performed during ``__enter__``. Check ``fetch.html`` to see if
    it succeeded. Set ``fetch.title`` after parsing so it's captured in the log::

        with tracked_fetch(tool, url, source_url=post_url, source_platform="bluesky") as fetch:
            if fetch.html is None:
                return None
            metadata = html.extract_metadata(fetch.html)
            fetch.title = metadata.title
            return FeedItem(...)
    """
    return _FetchContext(tool, url, source_url, source_platform, db_path)


class _FetchContext:
    def __init__(self, tool, url, source_url, source_platform, db_path):
        self.tool = tool
        self.url = url
        self.source_url = source_url
        self.source_platform = source_platform
        self.db_path = db_path
        self.html: str | None = None
        self.title: str | None = None
        self.success: bool = False
        self.http_status: int | None = None
        self.error_message: str | None = None
        self._start: float = 0.0

    def __enter__(self) -> "_FetchContext":
        from .http import FetchError, fetch_url

        self._start = time.monotonic()
        try:
            self.html = fetch_url(self.url, timeout=8)
            self.success = True
        except FetchError as e:
            self.http_status = e.status_code
            self.error_message = str(e)
        except Exception as e:  # noqa: BLE001
            self.error_message = str(e)
        return self

    def __exit__(self, exc_type, exc_val, _tb):
        if self.tool.id is None:
            return False  # tool not registered — skip logging silently

        duration_ms = int((time.monotonic() - self._start) * 1000)
        domain = urlparse(self.url).netloc or None

        try:
            import duckdb

            path = _resolve_db_path(self.db_path)
            conn = duckdb.connect(str(path))
            try:
                _ensure_schema(conn)
                conn.execute(
                    _INSERT_FETCH,
                    [
                        self.tool.id,
                        self.url,
                        domain,
                        self.source_url,
                        self.source_platform,
                        self.success,
                        self.http_status,
                        self.error_message,
                        duration_ms,
                        self.title,
                    ],
                )
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            pass  # never raise from __exit__
        return False
