"""the doc-site crawler: gitbook, quartz, and similar wikis. fetches pages
under a hard site-root boundary with a page budget. a map that names what it
did not read beats one that ran out of time: unvisited links are reported."""

from collections import deque
from urllib.parse import urlparse

import httpx

from .html import extract_links, html_to_text, same_root


async def crawl(root_url: str, budget: int = 30, client: httpx.AsyncClient | None = None) -> dict:
    """returns {pages: [{url, text}], report}. the report carries visited
    count, external links refused, off-root links refused, and unread links
    left when the budget filled. links outside the root are never followed."""
    queue: deque[str] = deque([root_url])
    seen: set[str] = set()
    pages: list[dict] = []
    external = 0
    off_root = 0
    root_netloc = urlparse(root_url).netloc
    own = client
    if own is None:
        own = httpx.AsyncClient(timeout=30, follow_redirects=True)
    try:
        while queue and len(pages) < budget:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            try:
                r = await own.get(url)
            except httpx.HTTPError:
                continue
            if r.status_code != 200:
                continue
            if "html" not in r.headers.get("content-type", "text/html"):
                continue
            final_url = str(r.url)
            text = html_to_text(r.text)
            if text:
                pages.append({"url": final_url, "text": text})
            for link in extract_links(r.text, final_url):
                if link in seen:
                    continue
                if same_root(root_url, link):
                    queue.append(link)
                else:
                    seen.add(link)
                    if urlparse(link).netloc == root_netloc:
                        off_root += 1
                    else:
                        external += 1
    finally:
        if client is None:
            await own.aclose()
    return {
        "pages": pages,
        "report": {
            "root": root_url,
            "budget": budget,
            "visited": len(pages),
            "skipped_external": external,
            "skipped_off_root": off_root,
            "unread_budget": [u for u in queue if u not in seen],
        },
    }
