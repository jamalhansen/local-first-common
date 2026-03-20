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
