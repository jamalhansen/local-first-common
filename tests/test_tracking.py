"""Tests for local_first_common.tracking."""

import time
import warnings
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

from local_first_common.tracking import (
    Tool,
    _resolve_db_path,
    log_run,
    register_tool,
    timed_run,
    tracked_fetch,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_count(db_path: Path, table: str = "processing_log") -> int:
    conn = duckdb.connect(str(db_path))
    try:
        result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return result[0]
    finally:
        conn.close()


def _last_row(db_path: Path, table: str = "processing_log") -> dict:
    conn = duckdb.connect(str(db_path))
    try:
        cur = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 1")
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
        assert row["xml_fallbacks"] is None
        assert row["parse_errors"] is None

    def test_xml_fallbacks_stored(self, tmp_path):
        db = tmp_path / "test.duckdb"
        log_run("tool", "model", xml_fallbacks=3, db_path=db)
        row = _last_row(db)
        assert row["xml_fallbacks"] == 3

    def test_parse_errors_stored(self, tmp_path):
        db = tmp_path / "test.duckdb"
        log_run("tool", "model", parse_errors=2, db_path=db)
        row = _last_row(db)
        assert row["parse_errors"] == 2

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

    def test_xml_fallbacks_via_context_manager(self, tmp_path):
        db = tmp_path / "test.duckdb"
        with timed_run("tool", "model", db_path=db) as run:
            run.xml_fallbacks = 5
        row = _last_row(db)
        assert row["xml_fallbacks"] == 5

    def test_parse_errors_via_context_manager(self, tmp_path):
        db = tmp_path / "test.duckdb"
        with timed_run("tool", "model", db_path=db) as run:
            run.parse_errors = 1
        row = _last_row(db)
        assert row["parse_errors"] == 1

    def test_xml_fallbacks_defaults_to_none(self, tmp_path):
        db = tmp_path / "test.duckdb"
        with timed_run("tool", "model", db_path=db):
            pass
        row = _last_row(db)
        assert row["xml_fallbacks"] is None

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


# ---------------------------------------------------------------------------
# register_tool
# ---------------------------------------------------------------------------

class TestRegisterTool:
    def test_returns_tool_with_id(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("my-tool", db_path=db)
        assert isinstance(tool, Tool)
        assert tool.name == "my-tool"
        assert tool.id is not None
        assert isinstance(tool.id, int)

    def test_idempotent_same_id(self, tmp_path):
        db = tmp_path / "test.duckdb"
        t1 = register_tool("my-tool", db_path=db)
        t2 = register_tool("my-tool", db_path=db)
        assert t1.id == t2.id

    def test_different_tools_different_ids(self, tmp_path):
        db = tmp_path / "test.duckdb"
        t1 = register_tool("tool-a", db_path=db)
        t2 = register_tool("tool-b", db_path=db)
        assert t1.id != t2.id

    def test_returns_tool_with_none_id_on_bad_path(self):
        tool = register_tool("my-tool", db_path="/nonexistent/bad/path.duckdb")
        assert tool.name == "my-tool"
        assert tool.id is None

    def test_tool_row_in_db(self, tmp_path):
        db = tmp_path / "test.duckdb"
        register_tool("content-discovery-agent", db_path=db)
        row = _last_row(db, table="tools")
        assert row["name"] == "content-discovery-agent"
        assert row["first_seen"] is not None


# ---------------------------------------------------------------------------
# tracked_fetch context manager
# ---------------------------------------------------------------------------

class TestTrackedFetch:
    def test_successful_fetch_logged(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)

        with patch("local_first_common.http.fetch_url", return_value="<html>hello</html>"):
            with tracked_fetch(tool, "https://example.com/article",
                               source_url="https://bsky.app/post/123",
                               source_platform="bluesky",
                               db_path=db) as fetch:
                fetch.title = "Example Article"

        assert fetch.html == "<html>hello</html>"
        assert fetch.success is True

        row = _last_row(db, table="fetch_log")
        assert row["tool_id"] == tool.id
        assert row["url"] == "https://example.com/article"
        assert row["domain"] == "example.com"
        assert row["source_url"] == "https://bsky.app/post/123"
        assert row["source_platform"] == "bluesky"
        assert row["success"] is True
        assert row["http_status"] is None
        assert row["title"] == "Example Article"
        assert row["duration_ms"] >= 0

    def test_http_error_logged(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)

        from local_first_common.http import FetchError
        with patch("local_first_common.http.fetch_url",
                   side_effect=FetchError("403 Forbidden", status_code=403)):
            with tracked_fetch(tool, "https://example.com/blocked",
                               source_platform="mastodon",
                               db_path=db) as fetch:
                pass  # fetch.html is None

        assert fetch.html is None
        assert fetch.success is False
        assert fetch.http_status == 403

        row = _last_row(db, table="fetch_log")
        assert row["success"] is False
        assert row["http_status"] == 403
        assert "403" in row["error_message"]

    def test_network_error_logged(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)

        from local_first_common.http import FetchError
        with patch("local_first_common.http.fetch_url",
                   side_effect=FetchError("Read timed out", status_code=None)):
            with tracked_fetch(tool, "https://slow.example.com/", db_path=db):
                pass

        row = _last_row(db, table="fetch_log")
        assert row["success"] is False
        assert row["http_status"] is None
        assert "timed out" in row["error_message"]

    def test_skips_logging_when_tool_id_none(self, tmp_path):
        db = tmp_path / "test.duckdb"
        # Ensure schema exists so _row_count doesn't fail
        register_tool("seed", db_path=db)
        tool = Tool(name="unregistered", id=None)

        with patch("local_first_common.http.fetch_url", return_value="<html/>"):
            with tracked_fetch(tool, "https://example.com/", db_path=db):
                pass

        # Only the seed tool row; no fetch_log rows
        assert _row_count(db, table="fetch_log") == 0

    def test_does_not_suppress_body_exceptions(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)

        with patch("local_first_common.http.fetch_url", return_value="<html/>"):
            with pytest.raises(ValueError, match="caller error"):
                with tracked_fetch(tool, "https://example.com/", db_path=db):
                    raise ValueError("caller error")

    def test_duration_ms_recorded(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)

        with patch("local_first_common.http.fetch_url", return_value="<html/>"):
            with tracked_fetch(tool, "https://example.com/", db_path=db):
                pass

        row = _last_row(db, table="fetch_log")
        assert row["duration_ms"] >= 0

    def test_source_url_and_platform_stored(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)

        with patch("local_first_common.http.fetch_url", return_value="<html/>"):
            with tracked_fetch(tool, "https://example.com/",
                               source_url="https://mastodon.social/@user/post/999",
                               source_platform="mastodon",
                               db_path=db):
                pass

        row = _last_row(db, table="fetch_log")
        assert row["source_url"] == "https://mastodon.social/@user/post/999"
        assert row["source_platform"] == "mastodon"
