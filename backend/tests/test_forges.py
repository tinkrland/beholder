"""forge adapter tests: gitlab, bitbucket, gitea against mock transports, the
registry, connected accounts, and token resolution. no network anywhere."""

import httpx
import pytest

from app.ingest.bitbucket import BitbucketForge
from app.ingest.forge import forge_for_url, forge_name_for_url, parse_repo_url
from app.ingest.gitea import GiteaForge
from app.ingest.gitlab import GitlabForge
from app.ingest.repo_walk import walk_repo


# ---------- registry ----------

def test_forge_detection_by_host():
    assert forge_name_for_url("https://github.com/o/r") == "github"
    assert forge_name_for_url("https://gitlab.com/o/r") == "gitlab"
    assert forge_name_for_url("https://bitbucket.org/o/r") == "bitbucket"
    assert forge_name_for_url("https://gitea.com/o/r") == "gitea"


def test_forge_override_for_self_hosted_instances():
    # a self-hosted gitea can live on any host: the explicit override wins
    assert forge_name_for_url("https://git.internal.dev/o/r", override="gitea") == "gitea"
    assert isinstance(forge_for_url("https://git.internal.dev/o/r", override="gitea"), GiteaForge)
    with pytest.raises(ValueError, match="unknown forge"):
        forge_name_for_url("https://x.dev/o/r")


def test_self_hosted_url_from_settings(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "gitea_url", "https://gite.tinkr.dev/api/v1")
    assert forge_name_for_url("https://gite.tinkr.dev/o/r") == "gitea"
    monkeypatch.setattr(settings, "gitlab_url", "https://git.tinkr.dev/api/v4")
    assert forge_name_for_url("https://git.tinkr.dev/o/r") == "gitlab"


def test_parse_repo_url_shapes():
    assert parse_repo_url("https://gitlab.com/o/r") == ("o", "r")
    assert parse_repo_url("git@github.com:o/r.git") == ("o", "r")


# ---------- gitlab ----------

def _gitlab_transport(seen_headers: dict | None = None) -> httpx.MockTransport:
    pid = "o%2Fr"

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if seen_headers is not None:
            seen_headers.update(dict(request.headers))
        if "/repository/commits/main" in url:
            return httpx.Response(200, json={"id": "shagitlab1"})
        if "/repository/tree" in url:
            return httpx.Response(200, json=[
                {"type": "blob", "path": "readme.md", "size": 100},
                {"type": "tree", "path": "src"},
            ])
        if "/repository/branches" in url:
            return httpx.Response(200, json=[{"name": "main"}])
        if "/repository/tags" in url:
            return httpx.Response(200, json=[{"name": "v1"}])
        if "/repository/files/readme.md/raw" in url:
            return httpx.Response(200, text="the project ships a deterministic engine")
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_gitlab_adapter_protocol():
    forge = GitlabForge(token="glpat-x", transport=_gitlab_transport())
    repo = "o/r"
    assert forge.list_refs(repo) == ["main", "v1"]
    tree = forge.list_tree(repo, "main")
    assert tree == [{"path": "readme.md", "size": 100, "commit_sha": "shagitlab1"}]  # trees are filtered out
    blob = forge.fetch_blob(repo, "main", "readme.md")
    assert "deterministic engine" in blob["content"]


def test_gitlab_walk_through_the_same_walk():
    forge = GitlabForge(token="glpat-x", transport=_gitlab_transport())
    result = walk_repo("https://gitlab.com/o/r", "main", forge=forge)
    assert result["report"]["commit_sha"] == "shagitlab1"
    assert any(c["path"] == "readme.md" for c in result["chunks"])


# ---------- bitbucket ----------

def _bitbucket_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/commit/main" in url:
            return httpx.Response(200, json={"hash": "shabit1"})
        if "/src/main/readme.md" in url:
            return httpx.Response(200, text="the readme names the beachhead segment")
        if "/src/main" in url:
            return httpx.Response(200, json={"values": [
                {"type": "commit_file", "path": "readme.md", "size": 100},
                {"type": "commit_directory", "path": "src"},
            ]})
        if "/refs/branches" in url:
            return httpx.Response(200, json={"values": [{"name": "main"}]})
        if "/refs/tags" in url:
            return httpx.Response(200, json={"values": [{"name": "v1"}]})
        if "/src/main/readme.md" in url:
            return httpx.Response(200, text="the readme names the beachhead segment")
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_bitbucket_adapter_protocol():
    forge = BitbucketForge(token="dXNlcjphcHAK", transport=_bitbucket_transport())
    assert forge.list_refs("o/r") == ["main", "v1"]
    tree = forge.list_tree("o/r", "main")
    assert tree[0]["commit_sha"] == "shabit1" and tree[0]["path"] == "readme.md"
    assert "beachhead segment" in forge.fetch_blob("o/r", "main", "readme.md")["content"]


# ---------- gitea ----------

def _gitea_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/git/commits/main" in url:
            return httpx.Response(200, json={"sha": "shagitea1"})
        if "/git/trees/" in url:
            return httpx.Response(200, json={"entries": [
                {"type": "blob", "path": "readme.md", "size": 100},
                {"type": "tree", "path": "src"},
            ], "truncated": False})
        if "/repos/o/r/branches" in url:
            return httpx.Response(200, json=[{"name": "main"}])
        if "/repos/o/r/tags" in url:
            return httpx.Response(200, json=[{"name": "v1"}])
        if "/raw/readme.md" in url:
            return httpx.Response(200, text="the growth docs state the icp")
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_gitea_adapter_protocol():
    forge = GiteaForge(token="gtx", transport=_gitea_transport())
    assert forge.list_refs("o/r") == ["main", "v1"]
    tree = forge.list_tree("o/r", "main")
    assert tree[0]["commit_sha"] == "shagitea1"
    assert "growth docs" in forge.fetch_blob("o/r", "main", "readme.md")["content"]


# ---------- connected accounts ----------

async def test_account_upsert_list_revoke_and_token_priority(db_session):
    from app.models import Project, ProjectMember, User
    from app.service import delete_forge_account, list_forge_accounts, resolve_forge_token, upsert_forge_account

    user = User(auth_id="t", email="t@t.dev")
    db_session.add(user)
    await db_session.commit()

    await upsert_forge_account(db_session, user.id, "github", "token-one")
    await upsert_forge_account(db_session, user.id, "github", "token-two")  # rotation replaces
    rows = await list_forge_accounts(db_session, user.id)
    assert len(rows) == 1 and rows[0].token == "token-two"

    # priority: explicit > account > env
    assert await resolve_forge_token(db_session, user.id, "github") == "token-two"
    assert await resolve_forge_token(db_session, user.id, "github", "explicit") == "explicit"
    assert await resolve_forge_token(db_session, user.id, "gitlab") is None

    assert await delete_forge_account(db_session, user.id, "github") is True
    assert await delete_forge_account(db_session, user.id, "github") is False
    assert await resolve_forge_token(db_session, user.id, "github") is None


async def test_unknown_forge_rejected(db_session):
    from app.service import upsert_forge_account

    with pytest.raises(ValueError, match="unknown forge"):
        await upsert_forge_account(db_session, "u", "sourceforge", "t")
