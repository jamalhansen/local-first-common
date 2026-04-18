import logging
from datetime import datetime, timedelta, timezone

import duckdb

from local_first_common.logging import purge_old_logs, setup_logging


def _fetch_all(db_path: str, query: str):
    conn = duckdb.connect(db_path)
    try:
        return conn.execute(query).fetchall()
    finally:
        conn.close()


class TestOperationalLogging:
    def test_warning_is_persisted(self, tmp_path, monkeypatch):
        db_path = tmp_path / "ops.duckdb"
        monkeypatch.setenv("LOCAL_FIRST_TRACKING_DB", str(db_path))

        setup_logging(tool_name="test-tool", persist_warnings=True)
        logging.getLogger("test.logger").warning("warning persisted")

        rows = _fetch_all(
            str(db_path),
            "SELECT level, tool_name, logger_name, message FROM operational_log",
        )
        assert len(rows) == 1
        assert rows[0][0] == "WARNING"
        assert rows[0][1] == "test-tool"
        assert rows[0][2] == "test.logger"
        assert rows[0][3] == "warning persisted"

    def test_exception_contains_traceback(self, tmp_path, monkeypatch):
        db_path = tmp_path / "ops.duckdb"
        monkeypatch.setenv("LOCAL_FIRST_TRACKING_DB", str(db_path))

        setup_logging(tool_name="test-tool", persist_warnings=True)
        logger = logging.getLogger("test.exception")

        try:
            raise RuntimeError("boom")
        except RuntimeError:
            logger.exception("captured")

        row = _fetch_all(
            str(db_path),
            "SELECT level, exception_type, traceback_text FROM operational_log ORDER BY id DESC LIMIT 1",
        )[0]
        assert row[0] == "ERROR"
        assert row[1] == "RuntimeError"
        assert "RuntimeError: boom" in row[2]

    def test_info_not_persisted(self, tmp_path, monkeypatch):
        db_path = tmp_path / "ops.duckdb"
        monkeypatch.setenv("LOCAL_FIRST_TRACKING_DB", str(db_path))

        setup_logging(tool_name="test-tool", persist_warnings=True)
        logging.getLogger("test.info").info("ignored info")

        rows = _fetch_all(str(db_path), "SELECT COUNT(*) FROM operational_log")
        assert rows[0][0] == 0

    def test_retention_purges_old_rows(self, tmp_path, monkeypatch):
        db_path = tmp_path / "ops.duckdb"
        monkeypatch.setenv("LOCAL_FIRST_TRACKING_DB", str(db_path))

        setup_logging(tool_name="test-tool", persist_warnings=True, retention_days=90)

        conn = duckdb.connect(str(db_path))
        try:
            old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).replace(
                tzinfo=None
            )
            conn.execute(
                """
                INSERT INTO operational_log
                    (level, tool_name, logger_name, module, function_name, line_no, message, created_at)
                VALUES ('WARNING', 'test-tool', 'manual', 'm', 'f', 1, 'old row', ?)
                """,
                [old_ts],
            )
        finally:
            conn.close()

        deleted = purge_old_logs(retention_days=90, db_path=str(db_path))
        assert deleted >= 1

        rows = _fetch_all(
            str(db_path),
            "SELECT COUNT(*) FROM operational_log WHERE message = 'old row'",
        )
        assert rows[0][0] == 0
