"""Tests for local_first_common.article_fetcher."""
from pathlib import Path
from unittest.mock import patch

from local_first_common.article_fetcher import (
    FeedItem,
    _is_blocked,
    fetch_article_metadata,
)
from local_first_common.http import FetchError

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_article.html"
SAMPLE_HTML = FIXTURE_PATH.read_text()

FALLBACK_HTML = """
<!DOCTYPE html>
<html><head>
  <title>Fallback Title Only</title>
  <meta name="description" content="Fallback description from meta tag." />
</head><body><p>Content.</p></body></html>
"""

NO_TITLE_HTML = """
<!DOCTYPE html>
<html><head><meta property="og:description" content="No title here." /></head>
<body></body></html>
"""


class TestFeedItem:
    def test_required_fields(self):
        item = FeedItem(title="T", description="D", url="https://example.com", source="example.com")
        assert item.title == "T"
        assert item.description == "D"
        assert item.url == "https://example.com"
        assert item.source == "example.com"

    def test_published_defaults_to_empty(self):
        item = FeedItem(title="T", description="D", url="u", source="s")
        assert item.published == ""

    def test_found_at_defaults_to_none(self):
        item = FeedItem(title="T", description="D", url="u", source="s")
        assert item.found_at is None

    def test_discovery_metadata_defaults_to_none(self):
        item = FeedItem(title="T", description="D", url="u", source="s")
        assert item.search_term is None
        assert item.platform is None


class TestFetchArticleMetadata:
    def test_extracts_og_title_and_og_description(self):
        with patch("local_first_common.http.fetch_url", return_value=SAMPLE_HTML):
            item = fetch_article_metadata("https://duckdb.org/article")

        assert item is not None
        assert item.title == "Understanding DuckDB: A Practical Guide"
        assert item.description == "A comprehensive guide to using DuckDB for fast in-process data analysis."

    def test_source_is_netloc(self):
        with patch("local_first_common.http.fetch_url", return_value=SAMPLE_HTML):
            item = fetch_article_metadata("https://duckdb.org/article")

        assert item is not None
        assert item.source == "duckdb.org"

    def test_extracts_article_published_time(self):
        with patch("local_first_common.http.fetch_url", return_value=SAMPLE_HTML):
            item = fetch_article_metadata("https://duckdb.org/article")

        assert item is not None
        assert item.published == "2026-02-15"

    def test_published_empty_when_no_date_meta(self):
        with patch("local_first_common.http.fetch_url", return_value=FALLBACK_HTML):
            item = fetch_article_metadata("https://example.com/page")

        assert item is not None
        assert item.published == ""

    def test_url_is_preserved(self):
        url = "https://duckdb.org/2026/02/05/release.html"
        with patch("local_first_common.http.fetch_url", return_value=SAMPLE_HTML):
            item = fetch_article_metadata(url)

        assert item is not None
        assert item.url == url

    def test_found_at_is_none_when_no_source_url(self):
        with patch("local_first_common.http.fetch_url", return_value=SAMPLE_HTML):
            item = fetch_article_metadata("https://duckdb.org/article")

        assert item is not None
        assert item.found_at is None

    def test_found_at_is_set_from_source_url(self):
        post_url = "https://bsky.app/profile/user.bsky.social/post/abc123"
        with patch("local_first_common.http.fetch_url", return_value=SAMPLE_HTML):
            item = fetch_article_metadata("https://duckdb.org/article", source_url=post_url)

        assert item is not None
        assert item.found_at == post_url

    def test_discovery_metadata_is_passed_through(self):
        with patch("local_first_common.http.fetch_url", return_value=SAMPLE_HTML):
            item = fetch_article_metadata(
                "https://duckdb.org/article",
                search_term="duckdb",
                source_platform="bluesky"
            )

        assert item is not None
        assert item.search_term == "duckdb"
        assert item.platform == "bluesky"

    def test_falls_back_to_title_tag_when_no_og_title(self):
        with patch("local_first_common.http.fetch_url", return_value=FALLBACK_HTML):
            item = fetch_article_metadata("https://example.com/page")

        assert item is not None
        assert item.title == "Fallback Title Only"

    def test_falls_back_to_meta_description_when_no_og_description(self):
        with patch("local_first_common.http.fetch_url", return_value=FALLBACK_HTML):
            item = fetch_article_metadata("https://example.com/page")

        assert item is not None
        assert item.description == "Fallback description from meta tag."

    def test_returns_none_when_no_title_found(self):
        with patch("local_first_common.http.fetch_url", return_value=NO_TITLE_HTML):
            item = fetch_article_metadata("https://example.com/no-title")

        assert item is None

    def test_returns_none_on_connection_error(self):
        with patch("local_first_common.http.fetch_url", side_effect=FetchError("connection error")):
            item = fetch_article_metadata("https://unreachable.example.com/")

        assert item is None

    def test_returns_none_on_http_error(self):
        with patch("local_first_common.http.fetch_url", side_effect=FetchError("404 Error", status_code=404)):
            item = fetch_article_metadata("https://example.com/missing")

        assert item is None

    def test_description_is_empty_string_when_none_available(self):
        no_desc_html = """
        <!DOCTYPE html><html><head>
          <meta property="og:title" content="Title Only" />
        </head><body></body></html>
        """
        with patch("local_first_common.http.fetch_url", return_value=no_desc_html):
            item = fetch_article_metadata("https://example.com/no-desc")

        assert item is not None
        assert item.title == "Title Only"
        assert item.description == ""


class TestIsBlocked:
    def test_exact_domain_match(self):
        assert _is_blocked("medium.com", frozenset({"medium.com"}))

    def test_subdomain_match(self):
        assert _is_blocked("username.medium.com", frozenset({"medium.com"}))

    def test_deep_subdomain_match(self):
        assert _is_blocked("ai.plainenglish.io", frozenset({"plainenglish.io"}))

    def test_no_match_for_unrelated_domain(self):
        assert not _is_blocked("simonwillison.net", frozenset({"medium.com"}))

    def test_no_partial_match(self):
        assert not _is_blocked("notmedium.com", frozenset({"medium.com"}))

    def test_strips_port(self):
        assert _is_blocked("medium.com:443", frozenset({"medium.com"}))

    def test_case_insensitive(self):
        assert _is_blocked("Medium.COM", frozenset({"medium.com"}))


class TestBlockedDomains:
    @patch("local_first_common.http.fetch_url")
    def test_blocked_domain_returns_none_without_fetching(self, mock_get):
        item = fetch_article_metadata("https://medium.com/some-user/some-article")
        assert item is None
        mock_get.assert_not_called()

    @patch("local_first_common.http.fetch_url")
    def test_blocked_subdomain_returns_none_without_fetching(self, mock_get):
        item = fetch_article_metadata("https://username.medium.com/article")
        assert item is None
        mock_get.assert_not_called()

    @patch("local_first_common.http.fetch_url")
    def test_blocked_medium_publication_returns_none(self, mock_get):
        item = fetch_article_metadata("https://ai.plainenglish.io/some-article")
        assert item is None
        mock_get.assert_not_called()

    @patch("local_first_common.http.fetch_url")
    def test_blocked_towardsdatascience_returns_none(self, mock_get):
        item = fetch_article_metadata("https://towardsdatascience.com/some-article")
        assert item is None
        mock_get.assert_not_called()

    @patch("local_first_common.http.fetch_url")
    def test_extra_blocked_domain_returns_none_without_fetching(self, mock_get):
        item = fetch_article_metadata(
            "https://nytimes.com/article",
            blocked_domains=frozenset({"nytimes.com"}),
        )
        assert item is None
        mock_get.assert_not_called()

    @patch("local_first_common.http.fetch_url")
    def test_unblocked_domain_proceeds_to_fetch(self, mock_get):
        mock_get.return_value = SAMPLE_HTML
        item = fetch_article_metadata("https://simonwillison.net/article")
        assert item is not None
        mock_get.assert_called_once()

    @patch("local_first_common.http.fetch_url")
    def test_non_http_scheme_returns_none_without_fetching(self, mock_get):
        item = fetch_article_metadata("ftp://files.example.com/doc.tar.gz")
        assert item is None
        mock_get.assert_not_called()

    @patch("local_first_common.http.fetch_url")
    def test_empty_url_returns_none_without_fetching(self, mock_get):
        item = fetch_article_metadata("")
        assert item is None
        mock_get.assert_not_called()
