from local_first_common.url import clean_url, normalize_url


class TestCleanUrl:
    def test_strips_utm_source(self):
        url = "https://example.com/article?utm_source=twitter"
        assert clean_url(url) == "https://example.com/article"

    def test_strips_multiple_utm_params(self):
        url = "https://example.com/post?utm_source=email&utm_medium=newsletter&utm_campaign=weekly"
        assert clean_url(url) == "https://example.com/post"

    def test_preserves_non_tracking_params(self):
        url = "https://example.com/search?q=python&page=2&utm_source=google"
        result = clean_url(url)
        # Sort order: page=2, q=python
        assert result == "https://example.com/search?page=2&q=python"

    def test_strips_fbclid(self):
        url = "https://example.com/page?fbclid=abc123"
        assert clean_url(url) == "https://example.com/page"

    def test_strips_gclid(self):
        url = "https://example.com/page?gclid=xyz789"
        assert clean_url(url) == "https://example.com/page"

    def test_strips_mc_eid(self):
        url = "https://example.com/post?mc_eid=abc&ref=newsletter"
        result = clean_url(url)
        assert "mc_eid" not in result
        assert "ref=newsletter" in result

    def test_no_query_params_unchanged(self):
        url = "https://example.com/article"
        assert clean_url(url) == url

    def test_invalid_url_returns_original(self):
        bad = "not a url !!!"
        assert clean_url(bad) == bad

    def test_preserves_fragment(self):
        # Fragment (#section) is preserved; utm param before the fragment is stripped
        url = "https://example.com/post?utm_source=rss#section"
        result = clean_url(url)
        assert "utm_source" not in result
        assert "#section" in result


class TestNormalizeUrl:
    def test_lowercases_scheme_and_netloc(self):
        url = "HTTPS://Example.COM/Page"
        assert normalize_url(url) == "https://example.com/Page"

    def test_strips_trailing_slash(self):
        url = "https://example.com/path/"
        assert normalize_url(url) == "https://example.com/path"

    def test_preserves_root_slash_as_empty(self):
        # urlparse("https://example.com/").path is "/"
        # rstrip("/") makes it ""
        url = "https://example.com/"
        assert normalize_url(url) == "https://example.com"

    def test_cleans_tracking_params(self):
        url = "https://example.com/path/?utm_source=twitter"
        assert normalize_url(url) == "https://example.com/path"

    def test_forces_https_for_hn(self):
        url = "http://news.ycombinator.com/item?id=123"
        assert normalize_url(url) == "https://news.ycombinator.com/item?id=123"

    def test_handles_complex_hn_url(self):
        url = "HTTP://news.ycombinator.com/ITEM?id=456&utm_source=social/"
        # item becomes lowercased if it was part of netloc, but it's part of path.
        # normalize_url only lowercases scheme and netloc.
        assert normalize_url(url) == "https://news.ycombinator.com/ITEM?id=456"
