"""Tests for api_call_log wiring in local_first_common.social.{mastodon,bluesky}."""
from unittest.mock import MagicMock, patch

import duckdb
import requests

from local_first_common.social import bluesky, mastodon
from local_first_common.tracking import register_tool


def _last_row(db_path, table: str = "api_call_log") -> dict:
    conn = duckdb.connect(str(db_path))
    try:
        cur = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 1")
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row))
    finally:
        conn.close()


class TestMastodonLogging:
    def test_fetch_posts_logs_success(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.status_code = 200
        resp.json.return_value = [{"id": "1"}, {"id": "2"}]
        with patch("local_first_common.social.mastodon.requests.get", return_value=resp):
            posts = mastodon.fetch_posts(["python"], instances=["fosstodon.org"], tool=tool, db_path=db)

        assert len(posts) == 2
        row = _last_row(db)
        assert row["service"] == "mastodon"
        assert row["operation"] == "fetch_posts"
        assert row["success"] is True
        assert row["item_count"] == 2

    def test_fetch_posts_logs_failure(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)
        with patch(
            "local_first_common.social.mastodon.requests.get",
            side_effect=requests.ConnectionError("timeout"),
        ):
            posts = mastodon.fetch_posts(["python"], instances=["fosstodon.org"], tool=tool, db_path=db)

        assert posts == []
        row = _last_row(db)
        assert row["success"] is False
        assert "timeout" in row["error_message"]

    def test_no_tool_means_no_row(self, tmp_path):
        db = tmp_path / "test.duckdb"
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = []
        with patch("local_first_common.social.mastodon.requests.get", return_value=resp):
            mastodon.fetch_posts(["python"], instances=["fosstodon.org"])
        assert not db.exists()


class TestBlueskyLogging:
    def test_get_auth_token_logs_success(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.status_code = 200
        resp.json.return_value = {"accessJwt": "jwt123"}
        with patch("local_first_common.social.bluesky.requests.post", return_value=resp):
            token = bluesky.get_auth_token("me.bsky.social", "app-pass", tool=tool, db_path=db)

        assert token == "jwt123"
        row = _last_row(db)
        assert row["service"] == "bluesky"
        assert row["operation"] == "auth"
        assert row["success"] is True

    def test_get_auth_token_logs_failure(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)
        with patch(
            "local_first_common.social.bluesky.requests.post",
            side_effect=requests.ConnectionError("timeout"),
        ):
            token = bluesky.get_auth_token("me.bsky.social", "app-pass", tool=tool, db_path=db)

        assert token is None
        row = _last_row(db)
        assert row["success"] is False

    def test_fetch_posts_logs_item_count(self, tmp_path):
        db = tmp_path / "test.duckdb"
        tool = register_tool("test-tool", db_path=db)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.status_code = 200
        resp.json.return_value = {"posts": [{"uri": "at://1"}, {"uri": "at://2"}]}
        with patch("local_first_common.social.bluesky.requests.get", return_value=resp):
            posts = bluesky.fetch_posts(["ai"], token="jwt123", tool=tool, db_path=db)

        assert len(posts) == 2
        row = _last_row(db)
        assert row["operation"] == "fetch_posts"
        assert row["item_count"] == 2

    def test_no_tool_means_no_row(self, tmp_path):
        db = tmp_path / "test.duckdb"
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"posts": []}
        with patch("local_first_common.social.bluesky.requests.get", return_value=resp):
            bluesky.fetch_posts(["ai"])
        assert not db.exists()
