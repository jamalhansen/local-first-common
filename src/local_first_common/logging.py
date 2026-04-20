"""Standardized logging configuration for local-first AI tools."""

import json
import logging
import os
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.logging import RichHandler

_DEFAULT_SYNC_PATH = Path("~/sync/logging/error_log.duckdb").expanduser()
_DEFAULT_RETENTION_DAYS = 90

_CREATE_OPERATIONAL_LOG_SEQUENCE = (
    "CREATE SEQUENCE IF NOT EXISTS operational_log_id_seq START 1;"
)

_CREATE_OPERATIONAL_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS operational_log (
    id              BIGINT DEFAULT nextval('operational_log_id_seq') PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level           VARCHAR NOT NULL,
    tool_name       VARCHAR,
    logger_name     VARCHAR NOT NULL,
    module          VARCHAR,
    function_name   VARCHAR,
    line_no         INTEGER,
    message         VARCHAR NOT NULL,
    exception_type  VARCHAR,
    traceback_text  VARCHAR,
    source_location VARCHAR,
    run_context     VARCHAR,
    extra_json      JSON
);
"""

_INSERT_OPERATIONAL_LOG = """
INSERT INTO operational_log
    (level, tool_name, logger_name, module, function_name, line_no, message,
     exception_type, traceback_text, source_location, run_context, extra_json)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_DELETE_OLD_OPERATIONAL_LOG = """
DELETE FROM operational_log
WHERE created_at < ?;
"""

_STANDARD_RECORD_ATTRS = set(logging.makeLogRecord({}).__dict__.keys())


def _normalize_db_path(path: Path, *, default_filename: str) -> Path:
    if path.exists() and path.is_dir():
        return path / default_filename
    if path.suffix.lower() == ".duckdb":
        return path
    if not path.suffix:
        return path / default_filename
    return path


def resolve_log_db_path(db_path: str | Path | None = None) -> Path:
    """Resolve the DuckDB path used for operational logging."""
    if db_path:
        raw_path = Path(db_path).expanduser()
    elif env := os.environ.get("LOCAL_FIRST_ERROR_LOG_DB"):
        raw_path = Path(env).expanduser()
    else:
        raw_path = _DEFAULT_SYNC_PATH

    path = _normalize_db_path(raw_path, default_filename="error_log.duckdb")

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_retention_days(retention_days: int | None) -> int:
    if retention_days is not None:
        return max(1, retention_days)

    raw = os.environ.get("LOCAL_FIRST_LOG_RETENTION_DAYS")
    if not raw:
        return _DEFAULT_RETENTION_DAYS

    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_RETENTION_DAYS


def _safe_json_dump(payload: dict[str, Any]) -> str | None:
    if not payload:
        return None
    try:
        return json.dumps(payload, default=str)
    except Exception:
        return None


class OperationalLogHandler(logging.Handler):
    """Persist warning/error logs into the shared DuckDB operational_log table."""

    def __init__(
        self,
        *,
        tool_name: str | None = None,
        db_path: str | Path | None = None,
        retention_days: int = _DEFAULT_RETENTION_DAYS,
    ) -> None:
        super().__init__(level=logging.WARNING)
        self.tool_name = tool_name
        self.db_path = resolve_log_db_path(db_path)
        self.retention_days = retention_days
        self._ensure_schema_and_retention()

    def _connect(self):
        import duckdb

        return duckdb.connect(str(self.db_path))

    def _ensure_schema_and_retention(self) -> None:
        conn = self._connect()
        try:
            conn.execute(_CREATE_OPERATIONAL_LOG_SEQUENCE)
            conn.execute(_CREATE_OPERATIONAL_LOG_TABLE)
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
            conn.execute(_DELETE_OLD_OPERATIONAL_LOG, [cutoff.replace(tzinfo=None)])
        finally:
            conn.close()

    def _extract_extra(self, record: logging.LogRecord) -> str | None:
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _STANDARD_RECORD_ATTRS
            and k not in {"tool_name", "source_location", "run_context"}
        }
        return _safe_json_dump(extras)

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING:
            return

        exception_type = None
        traceback_text = None
        if record.exc_info:
            exc_type = record.exc_info[0]
            exception_type = exc_type.__name__ if exc_type else None
            traceback_text = "".join(traceback.format_exception(*record.exc_info))

        payload = [
            record.levelname,
            getattr(record, "tool_name", None) or self.tool_name,
            record.name,
            record.module,
            record.funcName,
            record.lineno,
            record.getMessage(),
            exception_type,
            traceback_text,
            getattr(record, "source_location", None),
            getattr(record, "run_context", None),
            self._extract_extra(record),
        ]

        conn = self._connect()
        try:
            conn.execute(_INSERT_OPERATIONAL_LOG, payload)
        except Exception:
            self.handleError(record)
        finally:
            conn.close()


def purge_old_logs(
    retention_days: int = _DEFAULT_RETENTION_DAYS,
    db_path: str | Path | None = None,
) -> int:
    """Purge operational_log rows older than retention_days."""
    path = resolve_log_db_path(db_path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, retention_days))

    import duckdb

    conn = duckdb.connect(str(path))
    try:
        conn.execute(_CREATE_OPERATIONAL_LOG_SEQUENCE)
        conn.execute(_CREATE_OPERATIONAL_LOG_TABLE)
        before = conn.execute("SELECT COUNT(*) FROM operational_log").fetchone()[0]
        conn.execute(_DELETE_OLD_OPERATIONAL_LOG, [cutoff.replace(tzinfo=None)])
        after = conn.execute("SELECT COUNT(*) FROM operational_log").fetchone()[0]
        return int(before - after)
    finally:
        conn.close()


def setup_logging(
    level: int = logging.INFO,
    show_path: bool = False,
    console: Optional[Console] = None,
    tool_name: str | None = None,
    persist_warnings: bool = True,
    retention_days: int | None = None,
    db_path: str | Path | None = None,
) -> None:
    """Configure global logging using Rich for pretty terminal output.

    Args:
        level: The logging level (e.g. logging.DEBUG).
        show_path: Whether to show the file path in log output.
        console: Optional Rich Console instance.
        tool_name: Tool identifier included in persisted warning/error rows.
        persist_warnings: Persist WARNING+ records to DuckDB when enabled.
        retention_days: Operational log retention window (defaults to 90 days).
        db_path: Optional explicit path for the DuckDB log file.
    """
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        force=True,
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                show_path=show_path,
                console=console,
                markup=True,
            )
        ],
    )

    if persist_warnings:
        resolved_retention_days = _resolve_retention_days(retention_days)
        try:
            handler = OperationalLogHandler(
                tool_name=tool_name,
                db_path=db_path,
                retention_days=resolved_retention_days,
            )
            logging.getLogger().addHandler(handler)
        except Exception:
            logging.getLogger(__name__).warning(
                "Persistent warning/error logging is unavailable.",
                extra={"tool_name": tool_name},
            )

    # Suppress verbose logs from noisy third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("ollama").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with the given name."""
    return logging.getLogger(name)


def log_exception(
    logger: logging.Logger,
    message: str,
    **context: Any,
) -> None:
    """Log an exception with optional structured context."""
    logger.exception(message, extra=context if context else None)
