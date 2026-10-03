"""Job heartbeats: a scheduled job says "still making progress" by touching a file.

process-doctor watches every com.localfirst.* LaunchAgent and, until 2026-10-03,
could only infer a hang from flat CPU. That misfires on exactly the jobs this fleet
runs most: ones that spend their time waiting on an LLM call or a network fetch.
From 2026-09-30 it killed the discovery run most mornings mid-scoring (16 s per
gateway call, ~7 s of CPU in 10 minutes) because waiting looks like hanging.

A heartbeat answers the real question. The job calls ``heartbeat()`` each time it
finishes a unit of work; process-doctor judges the job stuck only when the
heartbeat stops moving. Jobs that never heartbeat keep the old CPU heuristic.

Which job am I? launchd does not export its label, so the LaunchAgent plist sets
``LOCALFIRST_JOB_LABEL`` (e.g. ``com.localfirst.discovery-loop``) in its
``EnvironmentVariables``. ``heartbeat()`` with no label reads that; when it is
unset (an interactive run, a test) it does nothing, so no file is written for a
job process-doctor is not watching.

Files live in ``~/sync/local-first/heartbeats/<label>``; the mtime is the beat.
Override the directory with ``LOCALFIRST_HEARTBEAT_DIR``. Never raises: a
heartbeat failure must not take the job down with it.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

LABEL_ENV = "LOCALFIRST_JOB_LABEL"
DIR_ENV = "LOCALFIRST_HEARTBEAT_DIR"


def heartbeat_dir() -> Path:
    override = os.environ.get(DIR_ENV)
    return Path(override).expanduser() if override else Path.home() / "sync" / "local-first" / "heartbeats"


def heartbeat_path(label: str) -> Path:
    return heartbeat_dir() / label


def heartbeat(label: str | None = None) -> bool:
    """Record progress for this job. Returns whether a beat was written.

    With no label, uses ``LOCALFIRST_JOB_LABEL``; if that is unset too, this is a
    no-op (returns False), which is the normal case outside launchd.
    """
    label = label or os.environ.get(LABEL_ENV)
    if not label:
        return False
    try:
        path = heartbeat_path(label)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        now = time.time()
        os.utime(path, (now, now))
        return True
    except OSError:
        return False


def last_heartbeat(label: str) -> float | None:
    """Epoch seconds of the job's most recent beat, or None if it has never beaten."""
    try:
        return heartbeat_path(label).stat().st_mtime
    except OSError:
        return None
