"""Tests for html.py — metadata extraction and content cleaning."""

from local_first_common import html


def test_extract_metadata_og_tags():
    """Extracts metadata from OpenGraph tags."""
    content = """
    <html>
      <head>
        <meta property="og:title" content="The OG Title" />
        <meta property="og:description" content="The OG Description" />
        <meta property="article:published_time" content="2026-03-20T12:00:00Z" />
      </head>
      <body><h1>Title Tag</h1></body>
    </html>
    """
    meta = html.extract_metadata(content)
    assert meta.title == "The OG Title"
    assert meta.description == "The OG Description"
    assert meta.published_date == "2026-03-20"


def test_extract_metadata_fallback_tags():
    """Extracts metadata from standard meta/title tags when OG missing."""
    content = """
    <html>
      <head>
        <title>Standard Title - Site Name</title>
        <meta name="description" content="Standard Description" />
      </head>
      <body>Body</body>
    </html>
    """
    meta = html.extract_metadata(content)
    assert meta.title == "Standard Title"
    assert meta.description == "Standard Description"


def test_extract_main_content():
    """Cleans HTML and extracts main article text."""
    content = """
    <html>
      <head><style>.css { color: red; }</style></head>
      <body>
        <nav>Nav links</nav>
        <main>
          <article>
            <h1>Real Title</h1>
            <p>First paragraph.</p>
            <script>alert('noise')</script>
            <p>Second paragraph.</p>
          </article>
        </main>
        <footer>Footer</footer>
      </body>
    </html>
    """
    text = html.extract_main_content(content)
    assert "Real Title" in text
    assert "First paragraph." in text
    assert "Second paragraph." in text
    assert "Nav links" not in text
    assert "Footer" not in text
    assert "alert('noise')" not in text


class TestExtractOutboundLinks:
    def test_extracts_links_from_article_body(self):
        content = """
        <html><body>
          <nav><a href="https://example.com/nav-link">Nav</a></nav>
          <article>
            <p>See <a href="https://other.com/post">this post</a> for more.</p>
          </article>
          <footer><a href="https://example.com/footer-link">Footer</a></footer>
        </body></html>
        """
        links = html.extract_outbound_links(content, base_url="https://example.com/article")
        assert links == ["https://other.com/post"]

    def test_resolves_relative_links_against_base_url(self):
        content = """
        <article><a href="/other-post">Relative link</a></article>
        """
        links = html.extract_outbound_links(content, base_url="https://example.com/some/article")
        assert links == ["https://example.com/other-post"]

    def test_skips_fragment_only_links(self):
        content = '<article><a href="#section-2">Jump</a></article>'
        links = html.extract_outbound_links(content, base_url="https://example.com/article")
        assert links == []

    def test_skips_non_http_schemes(self):
        content = """
        <article>
          <a href="mailto:someone@example.com">Email</a>
          <a href="javascript:void(0)">JS</a>
          <a href="https://real-link.com/">Real</a>
        </article>
        """
        links = html.extract_outbound_links(content, base_url="https://example.com/article")
        assert links == ["https://real-link.com/"]

    def test_deduplicates_repeated_links_preserving_order(self):
        content = """
        <article>
          <a href="https://a.com/1">First</a>
          <a href="https://b.com/1">Second</a>
          <a href="https://a.com/1">First again</a>
        </article>
        """
        links = html.extract_outbound_links(content, base_url="https://example.com/article")
        assert links == ["https://a.com/1", "https://b.com/1"]

    def test_no_container_falls_back_to_whole_document(self):
        content = '<html><body><a href="https://a.com/1">Only link</a></body></html>'
        links = html.extract_outbound_links(content, base_url="https://example.com/article")
        assert links == ["https://a.com/1"]

    def test_empty_html_returns_empty_list(self):
        assert html.extract_outbound_links("", base_url="https://example.com/article") == []
