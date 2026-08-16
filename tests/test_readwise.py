"""Tests for the shared Readwise Reader integration module."""
from unittest.mock import MagicMock, patch

import requests

from local_first_common.readwise import list_reader_documents, save_to_readwise


class TestSaveToReadwise:
    def test_returns_true_on_201(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        with patch("local_first_common.readwise.requests.post", return_value=mock_resp) as mock_post:
            result = save_to_readwise("tok_abc", "https://example.com/article")
        assert result is True
        mock_post.assert_called_once()

    def test_returns_true_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("local_first_common.readwise.requests.post", return_value=mock_resp):
            result = save_to_readwise("tok_abc", "https://example.com/article")
        assert result is True

    def test_returns_false_on_non_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "rate limited"
        with patch("local_first_common.readwise.requests.post", return_value=mock_resp):
            result = save_to_readwise("tok_abc", "https://example.com/article")
        assert result is False

    def test_returns_false_on_network_error(self):
        with patch("local_first_common.readwise.requests.post", side_effect=requests.ConnectionError("timeout")):
            result = save_to_readwise("tok_abc", "https://example.com/article")
        assert result is False

    def test_returns_false_when_no_token(self):
        result = save_to_readwise("", "https://example.com/article")
        assert result is False

    def test_sends_url_in_payload(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        with patch("local_first_common.readwise.requests.post", return_value=mock_resp) as mock_post:
            save_to_readwise("tok_abc", "https://example.com/article")
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["url"] == "https://example.com/article"

    def test_sends_authorization_header(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        with patch("local_first_common.readwise.requests.post", return_value=mock_resp) as mock_post:
            save_to_readwise("tok_secret", "https://example.com/article")
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Token tok_secret"

    def test_optional_fields_omitted_when_empty(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        with patch("local_first_common.readwise.requests.post", return_value=mock_resp) as mock_post:
            save_to_readwise("tok_abc", "https://example.com/article")
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert "title" not in payload
        assert "summary" not in payload
        assert "tags" not in payload
        assert "published_date" not in payload

    def test_optional_fields_included_when_provided(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        with patch("local_first_common.readwise.requests.post", return_value=mock_resp) as mock_post:
            save_to_readwise(
                "tok_abc",
                "https://example.com/article",
                title="My Article",
                summary="A great read.",
                tags=["python", "ai"],
                published_date="2026-03-13",
            )
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["title"] == "My Article"
        assert payload["summary"] == "A great read."
        assert payload["tags"] == ["python", "ai"]
        assert payload["published_date"] == "2026-03-13"

    def test_empty_tags_list_omitted(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        with patch("local_first_common.readwise.requests.post", return_value=mock_resp) as mock_post:
            save_to_readwise("tok_abc", "https://example.com/article", tags=[])
        _, kwargs = mock_post.call_args
        assert "tags" not in kwargs["json"]

    def test_includes_discovery_metadata_as_tags(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        with patch("local_first_common.readwise.requests.post", return_value=mock_resp) as mock_post:
            save_to_readwise(
                "tok_abc",
                "https://example.com/article",
                search_term="duckdb",
                platform="bluesky",
            )
        _, kwargs = mock_post.call_args
        tags = kwargs["json"]["tags"]
        assert "term:duckdb" in tags
        assert "platform:bluesky" in tags


def _page(results, next_cursor=None):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "count": len(results),
        "nextPageCursor": next_cursor,
        "results": results,
    }
    return mock_resp


_DOC = {
    "id": "abc123",
    "url": "https://read.readwise.io/read/abc123",
    "source_url": "https://example.com/original-article",
    "title": "An Article",
    "author": "Someone",
    "category": "article",
    "location": "new",
    "summary": "A short summary.",
    "published_date": "2026-03-11",
}


class TestListReaderDocuments:
    def test_returns_empty_when_no_token(self):
        result = list_reader_documents("")
        assert result == []

    def test_maps_document_fields_to_feed_item(self):
        with patch("local_first_common.readwise.requests.get", return_value=_page([_DOC])):
            result = list_reader_documents("tok_abc")
        assert len(result) == 1
        item = result[0]
        assert item.title == "An Article"
        assert item.description == "A short summary."
        assert item.url == "https://example.com/original-article"
        assert item.source == "readwise-reader"
        assert item.published == "2026-03-11"
        assert item.platform == "reader"

    def test_falls_back_to_reader_url_when_no_source_url(self):
        doc = dict(_DOC)
        del doc["source_url"]
        with patch("local_first_common.readwise.requests.get", return_value=_page([doc])):
            result = list_reader_documents("tok_abc")
        assert result[0].url == "https://read.readwise.io/read/abc123"

    def test_sends_authorization_header(self):
        with patch("local_first_common.readwise.requests.get", return_value=_page([])) as mock_get:
            list_reader_documents("tok_secret")
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == "Token tok_secret"

    def test_defaults_to_location_new(self):
        with patch("local_first_common.readwise.requests.get", return_value=_page([])) as mock_get:
            list_reader_documents("tok_abc")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["location"] == "new"

    def test_location_none_omits_filter(self):
        with patch("local_first_common.readwise.requests.get", return_value=_page([])) as mock_get:
            list_reader_documents("tok_abc", location=None)
        _, kwargs = mock_get.call_args
        assert "location" not in kwargs["params"]

    def test_optional_filters_included_when_provided(self):
        with patch("local_first_common.readwise.requests.get", return_value=_page([])) as mock_get:
            list_reader_documents(
                "tok_abc", category="article", updated_after="2026-01-01", tag="ai",
            )
        _, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["category"] == "article"
        assert params["updatedAfter"] == "2026-01-01"
        assert params["tag"] == "ai"

    def test_paginates_through_all_pages(self):
        page1 = _page([_DOC], next_cursor="cursor-2")
        page2 = _page([_DOC])
        with patch("local_first_common.readwise.requests.get", side_effect=[page1, page2]) as mock_get:
            result = list_reader_documents("tok_abc")
        assert len(result) == 2
        assert mock_get.call_count == 2
        second_call_params = mock_get.call_args_list[1].kwargs["params"]
        assert second_call_params["pageCursor"] == "cursor-2"

    def test_stops_and_returns_partial_results_on_page_failure(self):
        page1 = _page([_DOC], next_cursor="cursor-2")
        failing_resp = MagicMock()
        failing_resp.status_code = 500
        failing_resp.text = "server error"
        with patch("local_first_common.readwise.requests.get", side_effect=[page1, failing_resp]):
            result = list_reader_documents("tok_abc")
        assert len(result) == 1

    def test_returns_partial_results_on_network_error_mid_pagination(self):
        page1 = _page([_DOC], next_cursor="cursor-2")
        with patch(
            "local_first_common.readwise.requests.get",
            side_effect=[page1, requests.ConnectionError("timeout")],
        ):
            result = list_reader_documents("tok_abc")
        assert len(result) == 1
