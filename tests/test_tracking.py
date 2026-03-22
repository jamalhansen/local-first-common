"""Tests for local_first_common.tracking."""

import time
import warnings
from pathlib import Path

import duckdb
import pytest

from local_first_common.tracking import log_run, timed_run, _resolve_db_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_count(db_path: Path) -> int:
    conn = duckdb.connect(str(db_path))
    try:
        result = conn.execute("SELECT COUNT(*) FROM processing_log").fetchone()
        return result[0]
    finally:
        conn.close()


def _last_row(db_path: Path) -> dict:
    conn = duckdb.connect(str(db_path))
    try:
        cur = conn.execute("SELECT * FROM processing_log ORDER BY id DESC LIMIT 1")
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# _resolve_db_path
# ---------------------------------------------------------------------------

class TestResolveDbPath:
    def test_explicit_override_wins(self, tmp_path):
        override = tmp_path / "custom.duckdb"
        result = _resolve_db_path(override)
        assert result == override

    def test_env_var_wins_over_default(self, tmp_path, monkeypatch):
        env_path = tmp_path / "env.duckdb"
        monkeypatch.setenv("LOCAL_FIRST_TRACKING_DB", str(env_path))
        result = _resolve_db_path()
        assert result == env_path

    def test_creates_parent_dirs(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "tracking.duckdb"
        _resolve_db_path(deep)
        assert deep.parent.exists()

    def test_explicit_override_beats_env(self, tmp_path, monkeypatch):
        env_path = tmp_path / "env.duckdb"
        explicit = tmp_path / "explicit.duckdb"
        monkeypatch.setenv("LOCAL_FIRST_TRACKING_DB", str(env_path))
        result = _resolve_db_path(explicit)
        assert result == explicit


# ---------------------------------------------------------------------------
# log_run
# ---------------------------------------------------------------------------

class TestLogRun:
    def test_basic_insert(self, tmp_path):
        db = tmp_path / "test.duckdb"
        log_run("my-tool", "phi4-mini", db_path=db)
        assert _row_count(db) == 1

    def test_row_values(self, tmp_path):
        db = tmp_path / "test.duckdb"
        log_run(
            "resource-summarizer",
            "claude-haiku",
            source_location="https://example.com/article",
            item_count=3,
            input_tokens=100,
            output_tokens=200,
            duration_seconds=1.23,
            success=True,
            db_path=db,
        )
        row = _last_row(db)
        assert row["tool_name"] == "resource-summarizer"
        assert row["model"] == "claude-haiku"
        assert row["source_location"] == "https://example.com/article"
        assert row["item_count"] == 3
        assert row["input_tokens"] == 100
        assert row["output_tokens"] == 200
        assert abs(row["duration_seconds"] - 1.23) < 0.01
        assert row["success"] is True
        assert row["error_message"] is None

    def test_failure_row(self, tmp_path):
        db = tmp_path / "test.duckdb"
        log_run("my-tool", "phi4-mini", success=False, error_message="timeout", db_path=db)
        row = _last_row(db)
        assert row["success"] is False
        assert row["error_message"] == "timeout"

    def test_nullable_fields(self, tmp_path):
        db = tmp_path / "test.duckdb"
        log_run("tool", None, db_path=db)
        row = _last_row(db)
        assert row["model"] is None
        assert row["source_location"] is None
        assert row["item_count"] is None
        assert row["input_tokens"] is None
        assert row["output_tokens"] is None
        assert row["duration_seconds"] is None

    def test_item_count_stored(self, tmp_path):
        db = tmp_path / "test.duckdb"
        log_run("batch-tool", "phi4-mini", item_count=42, db_path=db)
        row = _last_row(db)
        assert row["item_count"] == 42

    def test_multiple_inserts_get_unique_ids(self, tmp_path):
        db = tmp_path / "test.duckdb"
        log_run("tool-a", "modelA", db_path=db)
        log_run("tool-b", "modelB", db_path=db)
        assert _row_count(db) == 2

    def test_never_raises_on_bad_path(self):
        """log_run must not raise even if the DB path is unwritable."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            log_run("tool", "model", db_path="/nonexistent/path/db.duckdb")
        # Should have emitted a warning
        assert any("log_run failed" in str(w.message) for w in caught)

    def test_created_at_is_set(self, tmp_path):
        db = tmp_path / "test.duckdb"
        log_run("tool", "model", db_path=db)
        row = _last_row(db)
        assert row["created_at"] is not None


# ---------------------------------------------------------------------------
# timed_run context manager
# ---------------------------------------------------------------------------

class TestTimedRun:
    def test_logs_on_success(self, tmp_path):
        db = tmp_path / "test.duckdb"
        with timed_run("my-tool", "phi4-mini", source_location="src.txt", db_path=db):
            time.sleep(0.01)
        row = _last_row(db)
        assert row["tool_name"] == "my-tool"
        assert row["success"] is True
        assert row["duration_seconds"] >= 0.01

    def test_item_count_via_context_manager(self, tmp_path):
        db = tmp_path / "test.duckdb"
        with timed_run("batch-tool", "phi4-mini", db_path=db) as run:
            run.item_count = 7
        row = _last_row(db)
        assert row["item_count"] == 7

    def test_item_count_defaults_to_none(self, tmp_path):
        db = tmp_path / "test.duckdb"
        with timed_run("tool", "model", db_path=db):
            pass
        row = _last_row(db)
        assert row["item_count"] is None

    def test_logs_on_exception(self, tmp_path):
        db = tmp_path / "test.duckdb"
        with pytest.raises(ValueError):
            with timed_run("failing-tool", "model", db_path=db):
                raise ValueError("boom")
        row = _last_row(db)
        assert row["success"] is False
        assert "boom" in row["error_message"]

    def test_does_not_suppress_exceptions(self, tmp_path):
        db = tmp_path / "test.duckdb"
        with pytest.raises(RuntimeError, match="expected"):
            with timed_run("tool", "model", db_path=db):
                raise RuntimeError("expected")

    def test_duration_is_positive(self, tmp_path):
        db = tmp_path / "test.duckdb"
        with timed_run("tool", "model", db_path=db):
            pass
        row = _last_row(db)
        assert row["duration_seconds"] >= 0.0
