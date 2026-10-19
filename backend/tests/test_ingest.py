"""ingest tests: excludes, secret redaction, the rest walk with a mocked forge."""

import base64
import json

import httpx

from app.ingest.excludes import Excludes, priority, select_tree
from app.ingest.forge import GithubForge, parse_repo_url
from app.ingest.repo_walk import chunk_text, walk_repo
from app.ingest.secrets import redact, scan


# ---------- excludes ----------

def test_default_excludes_hit_dependency_and_binary_paths():
    ex = Excludes()
    assert ex.is_excluded("node_modules/express/index.js")
    assert ex.is_excluded("src/logo.png")
    assert ex.is_excluded(".env")
    assert not ex.is_excluded("src/main.py")


def test_beholderignore_patterns():
    ex = Excludes("internal/\n*.spec.ts")
    assert ex.is_excluded("src/internal/x.py")
    assert ex.is_excluded("tests/a.spec.ts")
    assert not ex.is_excluded("src/main.py")


def test_readme_outranks_code():
    paths = ["src/z.py", "readme.md", "docs/guide.md"]
    selected, _ = select_tree(paths, Excludes(), budget=10)
    assert selected[0] == "readme.md"
    assert selected.index("docs/guide.md") < selected.index("src/z.py")


def test_budget_unread_is_reported():
    paths = [f"src/file{i}.py" for i in range(50)]
    selected, report = select_tree(paths, Excludes(), budget=10)
    assert len(selected) == 10
    assert len(report["unread_budget"]) == 40


# ---------- secrets ----------

def test_scan_and_redact_github_token():
    text = 'token = "ghp_' + "a" * 36 + '"'
    clean, had = redact(text)
    assert had
    assert "ghp_" not in clean
    assert "[REDACTED:github_token]" in clean


def test_redaction_keeps_line_count():
    text = 'api_key = "AKIA1234567890ABC12"\nline two\nline three'
    clean, _ = redact(text)
    assert len(clean.splitlines()) == 3  # provenance line numbers stay true


def test_clean_text_reports_no_secrets():
    assert redact("just normal code")[1] is False


# ---------- forge and walk ----------

def test_parse_repo_url():
    assert parse_repo_url("https://github.com/tinkrland/beholder") == ("tinkrland", "beholder")
    assert parse_repo_url("https://github.com/tinkrland/beholder.git") == ("tinkrland", "beholder")
    import pytest

    with pytest.raises(ValueError):
        parse_repo_url("https://github.com/onlyowner")


def _mock_forge() -> GithubForge:
    tree = [
        {"path": "readme.md", "type": "blob", "size": 100},
        {"path": "package.json", "type": "blob", "size": 80},
        {"path": "src/app.py", "type": "blob", "size": 40},
        {"path": "node_modules/x/index.js", "type": "blob", "size": 5},
        {"path": "assets/logo.png", "type": "blob", "size": 900},
        {"path": ".env", "type": "blob", "size": 30},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url.path
        if url.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "abc123"})
        if "/git/trees/" in url:
            return httpx.Response(200, json={"tree": tree})
        if "/contents/" in url:
            path = url.split("/contents/")[1]
            content = json.dumps({"deps": {"fastapi": "*"}}) if path == "package.json" else "hello\nworld\nsecret gh token ghp_" + "a" * 36 + " here"
            return httpx.Response(
                200,
                json={"path": path, "encoding": "base64", "content": base64.b64encode(content.encode()).decode(), "sha": "blobsha"},
            )
        return httpx.Response(404)

    return GithubForge(transport=httpx.MockTransport(handler))


def test_rest_walk_selects_excludes_reports():
    result = walk_repo("https://github.com/tinkrland/demo", "main", forge=_mock_forge())
    report = result["report"]
    paths = [c["path"] for c in result["chunks"]]
    assert "readme.md" in paths and "package.json" in paths and "src/app.py" in paths
    assert "node_modules/x/index.js" not in paths
    assert ".env" not in paths
    assert report["commit_sha"] == "abc123"
    assert report["repo"] == "tinkrland/demo"


def test_walk_redacts_before_any_chunk_stored():
    result = walk_repo("https://github.com/tinkrland/demo", "main", forge=_mock_forge())
    readme = [c for c in result["chunks"] if c["path"] == "readme.md"][0]
    assert "ghp_" not in readme["text"]
    assert readme["redacted"] is True


def test_chunk_text_line_ranges():
    chunks = chunk_text("\n".join(f"line {i}" for i in range(1, 301)), "big.py", "sha")
    assert chunks[0]["lines_start"] == 1 and chunks[0]["lines_end"] == 120
    assert chunks[2]["lines_start"] == 241 and chunks[2]["lines_end"] == 300
