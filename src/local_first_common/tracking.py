"""Processing run tracker — logs tool/model/source/timing/item count to a central DuckDB file.

Each local-first tool calls ``log_run()`` after completing an LLM call.  The
function is fire-and-forget: it never raises, so a tracking failure never
breaks a tool.

Default DB path: ``~/sync/local-first/processing_log.duckdb``
Override:        ``LOCAL_FIRST_TRACKING_DB`` environment variable

Typical usage (simple)::

    from local_first_common.tracking import log_run

    log_run("my-tool", llm.model, source_location=url, item_count=5,
            duration_seconds=1.23)

Typical usage (context manager — tracks timing + success automatically)::

    from local_first_common.tracking import timed_run

    with timed_run("my-tool", llm.model, source_location=url) as run:
        results = process_items(items)
        run.item_count = len(results)   # set at any point inside the block
"""

import os
import time
import warnings
from pathlib import Path

_DEFAULT_SYNC_PATH = Path("~/sync/local-first/processing_log.duckdb").expanduser()

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
