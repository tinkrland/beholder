"""stage 2 tests: docs and prose inputs, url sources, doc-site crawls.
no network: the crawler and firecrawl run on injected transports."""

import base64
import json

import httpx
import pytest

from app.ingest.docsite import crawl
from app.ingest.docs import parse_document, parse_direct_text, suffix_of
from app.ingest.firecrawl import FirecrawlClient
from app.ingest.html import extract_links, html_to_text, same_root


# ---------- html ----------

def test_html_to_text_drops_scripts_and_decodes_entities():
    html = "<html><script>evil()</script><body><h1>fast install</h1><p>safe &amp; reproducible</p></body></html>"
    text = html_to_text(html)
    assert "evil" not in text
    assert "fast install" in text and "safe & reproducible" in text


def test_extract_links_resolves_and_defragments():
    html = '<a href="/guide">a</a> <a href="https://x.dev/#top">b</a> <a href="mailto:x@y.z">c</a> <a href="javascript:void(0)">d</a> <a href="/guide">dup</a>'
    links = extract_links(html, "https://x.dev/docs/")
    assert "https://x.dev/guide" in links  # root-relative resolves against the host
    assert "https://x.dev/" in links  # fragment stripped, root stays root
    assert all("#" not in l for l in links)
    assert all(not l.startswith("mailto:") and not l.startswith("javascript:") for l in links)
    assert len(links) == len(set(links))


def test_same_root_boundary():
    assert same_root("https://x.dev/docs/", "https://x.dev/docs/page")
    assert not same_root("https://x.dev/docs/", "https://x.dev/blog")  # off root
    assert not same_root("https://x.dev/docs/", "https://other.dev/docs/")  # off host


# ---------- doc-site crawl ----------

def _site_transport() -> httpx.MockTransport:
    pages = {
        "https://x.dev/docs/": '<html><a href="/docs/intro">intro</a><a href="/docs/deep">deep</a><a href="https://ads.example.com/track">ad</a></html>',
        "https://x.dev/docs/intro": '<html><a href="/docs/deep#part">deep again</a><a href="/blog">blog</a></html>',
        "https://x.dev/docs/deep": "<html><p>the engine rebuilds geometry deterministically</p></html>",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in pages:
            return httpx.Response(200, text=pages[url], headers={"content-type": "text/html"})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_crawl_stays_under_the_root_and_budget():
    async with httpx.AsyncClient(transport=_site_transport()) as client:
        result = await crawl("https://x.dev/docs/", budget=10, client=client)
    urls = [p["url"] for p in result["pages"]]
    assert urls == ["https://x.dev/docs/", "https://x.dev/docs/intro", "https://x.dev/docs/deep"]
    assert "https://ads.example.com/track" not in urls
    report = result["report"]
    assert report["visited"] == 3 and report["skipped_external"] >= 1
    assert report["skipped_off_root"] >= 1  # /blog refused: outside the doc root
    assert not report["unread_budget"]


async def test_crawl_budget_reports_unread():
    async with httpx.AsyncClient(transport=_site_transport()) as client:
        result = await crawl("https://x.dev/docs/", budget=2, client=client)
    assert len(result["pages"]) == 2
    assert result["report"]["unread_budget"]  # a map that names what it did not read


# ---------- docs ----------

def test_direct_parse_chunks_with_doc_provenance():
    chunks = parse_direct_text("# the project\nrenders the exact product mesh", "readme.md")
    assert chunks[0]["kind"] == "doc" and chunks[0]["path"] == "readme.md"


def test_suffix_of():
    assert suffix_of("Spec.PDF") == ".pdf"
    assert suffix_of("noext") == ""


async def test_parse_document_rejects_misuse():
    with pytest.raises(ValueError, match="as text"):
        await parse_document("notes.md", content_b64="aGk=")
    with pytest.raises(ValueError, match="base64"):
        await parse_document("bad.pdf", content_b64="not-base64!!")


def _firecrawl() -> FirecrawlClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"markdown": "# parsed pdf\nthe project ships a deterministic engine"}})
    return FirecrawlClient(api_key="test-key", transport=httpx.MockTransport(handler))


async def test_pdf_goes_through_firecrawl():
    chunks = await parse_document("spec.pdf", content_b64=base64.b64encode(b"%PDF-fake").decode(), firecrawl=_firecrawl())
    assert chunks[0]["kind"] == "doc"
    assert "deterministic engine" in chunks[0]["text"]


def test_firecrawl_without_key_is_honest():
    client = FirecrawlClient(api_key=None)
    import asyncio

    async def go():
        try:
            await client.scrape_markdown("https://x.dev/paper.pdf")
            return False
        except RuntimeError as e:
            return "BEHOLDER_FIRECRAWL_KEY" in str(e)

    assert asyncio.run(go())


async def test_doc_source_extraction_keeps_doc_provenance(db_session):
    from app.service import add_doc_source, create_project, extract_facts
    from conftest import FakeRun

    from app.models import Project, ProjectMember, User

    user = User(auth_id="t", email="t@t.dev")
    db_session.add(user)
    await db_session.commit()
    project = Project(name="docs project")
    db_session.add(project)
    await db_session.flush()
    db_session.add(ProjectMember(project_id=project.id, user_id=user.id))
    await db_session.commit()

    await add_doc_source(db_session, project.id, "readme.md", text="# growth\nthe readme names made-to-order jewelers as the first segment")
    canned = FakeRun({"extract_facts": {"facts": [{"kind": "audience", "statement": "the readme names made-to-order jewelers as the first segment", "lines": [1, 2]}]}})
    facts = await extract_facts(db_session, project.id, canned)
    semantic = [f for f in facts if f.kind == "audience"]
    assert semantic and semantic[0].provenance[0]["type"] == "doc"
    assert semantic[0].provenance[0]["ref"] == "readme.md"
