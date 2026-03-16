from local_first_common.url import clean_url


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
        assert "q=python" in result
        assert "page=2" in result
        assert "utm_source" not in result

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
