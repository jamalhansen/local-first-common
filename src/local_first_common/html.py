import re
from typing import NamedTuple
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

def extract_main_content(html: str) -> str:
    """Extract the primary text content from an HTML string.
    
    Removes noise (nav, footer, script, etc.) and prefers <article> or <main> tags.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    # Selection priority
    container = None
    for selector in ["article", "main", "[role='main']", "body"]:
        container = soup.select_one(selector)
        if container:
            break

    if not container:
        container = soup

    text = container.get_text(separator="\n", strip=True)
    
    # Cleanup whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
