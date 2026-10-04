"""A second process holding processing_log.duckdb's write lock must not drop our row (2026-10-04)."""
import subprocess
import sys
import textwrap
import time

import duckdb

from local_first_common import tracking


def _hold_lock(path, seconds):
    """Hold the DuckDB write lock from a separate process, like the gateway does."""
    code = textwrap.dedent(f"""
        import duckdb, time
        c = duckdb.connect({str(path)!r})
        print("held", flush=True)
        time.sleep({seconds})
        c.close()
    """)
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "held"
    return proc


def test_log_run_waits_for_a_short_lock_instead_of_dropping_the_row(tmp_path):
    db = tmp_path / "log.duckdb"
    duckdb.connect(str(db)).close()
    tracking.get_tracking_write_stats(reset=True)
    holder = _hold_lock(db, 0.4)
    try:
        tracking.log_run("lock-test", "m", provider="p", duration_seconds=1.0, db_path=db)
    finally:
        holder.wait()
    stats = tracking.get_tracking_write_stats()
    assert stats["lock_retried"] >= 1
    assert stats["lock_gave_up"] == 0
    rows = duckdb.connect(str(db), read_only=True).execute(
        "SELECT tool_name FROM processing_log"
    ).fetchall()
    assert rows == [("lock-test",)]


def test_a_lock_held_past_the_backoff_is_counted_and_never_raises(tmp_path, monkeypatch):
    db = tmp_path / "log.duckdb"
    duckdb.connect(str(db)).close()
    monkeypatch.setattr(tracking, "_LOCK_RETRY_DELAYS", (0.01, 0.01))
    tracking.get_tracking_write_stats(reset=True)
    holder = _hold_lock(db, 1.0)
    try:
        start = time.monotonic()
        tracking.log_run("lock-test", "m", provider="p", db_path=db)  # must not raise
        assert time.monotonic() - start < 0.9
    finally:
        holder.wait()
    assert tracking.get_tracking_write_stats()["lock_gave_up"] == 1


def test_non_lock_errors_are_not_retried(tmp_path, monkeypatch):
    calls = []

    def boom(path):
        calls.append(path)
        raise duckdb.IOException("Cannot open file: permission denied")

    monkeypatch.setattr(duckdb, "connect", boom)
    try:
        tracking._connect_with_retry(tmp_path / "x.duckdb")
    except duckdb.IOException:
        pass
    assert len(calls) == 1
