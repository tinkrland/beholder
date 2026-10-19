"""html to text and link extraction, for the doc-site crawler. pure functions,
no parser dependency: doc sites (gitbook, quartz) are static html, and a small
deterministic extractor beats a heavy dependency for the mvp."""

import re
from urllib.parse import urldefrag, urljoin

_ENTITIES = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&nbsp;": " "}

_HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def html_to_text(html: str) -> str:
    """scripts and styles are dropped, tags become spaces, entities decoded,
    whitespace collapsed. line structure is lost on purpose: provenance for
    url sources is the url, not line numbers."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1\s*>", " ", html)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    for k, v in _ENTITIES.items():
        text = text.replace(k, v)
    return re.sub(r"[ \t]+", " ", text).strip()


def extract_links(html: str, base_url: str) -> list[str]:
    """absolute, defragmented http(s) links in document order, deduplicated."""
    out: list[str] = []
    seen: set[str] = set()
    for href in _HREF.findall(html):
        href = href.strip()
        if not href or href.startswith(("mailto:", "javascript:", "tel:", "#")):
            continue
        absolute, _ = urldefrag(urljoin(base_url, href))
        if not absolute.startswith(("http://", "https://")):
            continue
        if absolute not in seen:
            seen.add(absolute)
            out.append(absolute)
    return out


def same_root(root: str, url: str) -> bool:
    """hard site-root boundary: same host and the url stays under the root path.
    a crawl that wanders outside the doc root pollutes the project model."""
    from urllib.parse import urlparse

    r, u = urlparse(root), urlparse(url)
    if r.netloc != u.netloc or (r.scheme != u.scheme and "https" not in (r.scheme, u.scheme)):
        return False
    root_path = r.path.rstrip("/")
    return u.path.startswith(root_path) if root_path else True
