import os

from local_first_common import heartbeat as hb


def test_noop_without_label(tmp_path, monkeypatch):
    monkeypatch.setenv(hb.DIR_ENV, str(tmp_path))
    monkeypatch.delenv(hb.LABEL_ENV, raising=False)
    assert hb.heartbeat() is False
    assert list(tmp_path.iterdir()) == []


def test_explicit_label_writes_and_reads_back(tmp_path, monkeypatch):
    monkeypatch.setenv(hb.DIR_ENV, str(tmp_path / "beats"))
    assert hb.heartbeat("com.localfirst.x") is True
    beat = hb.last_heartbeat("com.localfirst.x")
    assert beat is not None
    assert (tmp_path / "beats" / "com.localfirst.x").exists()


def test_label_from_env_and_mtime_advances(tmp_path, monkeypatch):
    monkeypatch.setenv(hb.DIR_ENV, str(tmp_path))
    monkeypatch.setenv(hb.LABEL_ENV, "com.localfirst.discovery-loop")
    assert hb.heartbeat() is True
    path = tmp_path / "com.localfirst.discovery-loop"
    os.utime(path, (1_000_000, 1_000_000))  # pretend the last beat was long ago
    assert hb.last_heartbeat("com.localfirst.discovery-loop") == 1_000_000
    assert hb.heartbeat() is True
    beat = hb.last_heartbeat("com.localfirst.discovery-loop")
    assert beat is not None and beat > 1_000_000


def test_never_beaten_is_none(tmp_path, monkeypatch):
    monkeypatch.setenv(hb.DIR_ENV, str(tmp_path))
    assert hb.last_heartbeat("com.localfirst.nope") is None


def test_unwritable_dir_does_not_raise(tmp_path, monkeypatch):
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x")
    monkeypatch.setenv(hb.DIR_ENV, str(blocker / "beats"))
    assert hb.heartbeat("com.localfirst.x") is False
