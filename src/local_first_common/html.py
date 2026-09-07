import re
from typing import NamedTuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

class ArticleMetadata(NamedTuple):
    title: str
    description: str
    author: str = ""
    published_date: str = ""

def extract_metadata(html: str) -> ArticleMetadata:
    """Extract basic metadata from HTML meta tags.
    
    Priority:
      title:       og:title  -> <title>
      description: og:description -> <meta name="description">
      date:        article:published_time -> datePublished -> og:article:published_time
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Title
    og_title = soup.find("meta", attrs={"property": "og:title"})
    title = (og_title.get("content", "").strip() if og_title else "") or ""
    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        
    # Suffix stripping (e.g. "Post Title - Site Name")
    if title:
        title = re.split(r"\s[-|–]\s", title)[0].strip()

    # Description
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    description = (og_desc.get("content", "").strip() if og_desc else "") or ""
    if not description:
        desc_tag = soup.find("meta", attrs={"name": "description"})
        description = desc_tag.get("content", "").strip() if desc_tag else ""

    # Published date
    pub_meta = (
        soup.find("meta", attrs={"property": "article:published_time"})
        or soup.find("meta", attrs={"name": "datePublished"})
        or soup.find("meta", attrs={"property": "og:article:published_time"})
    )
    published = ""
    if pub_meta:
        raw = pub_meta.get("content", "").strip()
        if raw:
            published = raw[:10]  # ISO date truncate

    return ArticleMetadata(title=title, description=description, published_date=published)

def _select_content_container(soup: BeautifulSoup):
    """Strip chrome and return the element most likely to hold the article body.

    Shared by extract_main_content and extract_outbound_links so both agree on
    what counts as "the article" -- a link only counts as a citation if a
    human reading the piece would actually encounter it, not one buried in
    the same nav/footer chrome both functions already exclude.
    """
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    for selector in ["article", "main", "[role='main']", "body"]:
        container = soup.select_one(selector)
        if container:
            return container

    return soup


def extract_main_content(html: str) -> str:
    """Extract the primary text content from an HTML string.

    Removes noise (nav, footer, script, etc.) and prefers <article> or <main> tags.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = _select_content_container(soup)

    text = container.get_text(separator="\n", strip=True)

    # Cleanup whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_outbound_links(html: str, base_url: str) -> list[str]:
    """Return absolute http(s) links found within an article's main content.

    Uses the same container selection as extract_main_content, so links from
    navigation, footers, and sidebars are excluded -- only links a reader
    would actually encounter in the article body count. Relative links are
    resolved against base_url. Order is preserved; duplicates are dropped.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = _select_content_container(soup)

    links: list[str] = []
    seen: set[str] = set()
    for a in container.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
    return links
