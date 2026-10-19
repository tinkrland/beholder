"""forge adapters. one interface, three calls per forge:

    list_refs(repo) -> list[str]
    list_tree(repo, ref) -> list[{path, size}]
    fetch_blob(repo, ref, path) -> {content, commit_sha}

github is built; gitlab, bitbucket, and gitea follow the same interface, one
file each, per build order. adding a forge is a file, not a design change.
"""

import base64
import re
from typing import Any, Protocol

import httpx


class Forge(Protocol):
    def list_refs(self, repo: str) -> list[str]: ...
    def list_tree(self, repo: str, ref: str) -> list[dict[str, Any]]: ...
    def fetch_blob(self, repo: str, ref: str, path: str) -> dict[str, Any]: ...


def parse_repo_url(url: str) -> tuple[str, str]:
    """owner/repo from any common forge url shape: https, ssh, with or without .git."""
    cleaned = url.strip().rstrip("/")
    cleaned = re.sub(r"\.git$", "", cleaned)
    cleaned = re.sub(r"^[a-z]+://", "", cleaned)  # https://
    cleaned = cleaned.replace(":", "/")  # git@github.com:owner/repo
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) >= 3 and "." in parts[0]:  # host, owner, repo at minimum
        return parts[-2], parts[-1]
    raise ValueError(f"cannot parse repo url: {url}")


class GithubForge:
    """rest walk over github's api. no clone, ever. read-only."""

    API = "https://api.github.com"

    def __init__(self, token: str | None = None, transport: httpx.BaseTransport | None = None):
        self.headers = {"accept": "application/vnd.github+json"}
        if token:
            self.headers["authorization"] = f"bearer {token}"
        self.transport = transport  # tests inject a mock transport; prod never does

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.API, headers=self.headers, timeout=30, transport=self.transport)

    def list_refs(self, repo: str) -> list[str]:
        with self._client() as c:
            branches = c.get(f"/repos/{repo}/branches?per_page=100")
            branches.raise_for_status()
            tags = c.get(f"/repos/{repo}/tags?per_page=100")
            tags.raise_for_status()
        return [b["name"] for b in branches.json()] + [t["name"] for t in tags.json()]

    def list_tree(self, repo: str, ref: str) -> list[dict[str, Any]]:
        with self._client() as c:
            # resolve the ref to a commit sha once, so every blob citation
            # carries the same sha
            r = c.get(f"/repos/{repo}/commits/{ref}")
            r.raise_for_status()
            sha = r.json()["sha"]
            t = c.get(f"/repos/{repo}/git/trees/{sha}", params={"recursive": "1"})
            t.raise_for_status()
        return [
            {"path": e["path"], "size": e.get("size", 0), "commit_sha": sha}
            for e in t.json().get("tree", [])
            if e["type"] == "blob"
        ]

    def fetch_blob(self, repo: str, ref: str, path: str) -> dict[str, Any]:
        with self._client() as c:
            r = c.get(f"/repos/{repo}/contents/{path}", params={"ref": ref})
            r.raise_for_status()
            data = r.json()
        content = data.get("content", "")
        if data.get("encoding") == "base64":
            content = base64.b64decode(content).decode("utf-8", errors="replace")
        return {"content": content, "commit_sha": data.get("sha", "")}

# ---------- the forge registry ----------

from urllib.parse import urlparse

from ..config import settings
from .bitbucket import BitbucketForge
from .gitea import GiteaForge
from .gitlab import GitlabForge

KNOWN_HOSTS = {"github.com": "github", "gitlab.com": "gitlab", "bitbucket.org": "bitbucket", "gitea.com": "gitea"}
FORGES = {"github": GithubForge, "gitlab": GitlabForge, "bitbucket": BitbucketForge, "gitea": GiteaForge}


def _env_tokens() -> dict:
    return {
        "github": settings.github_token,
        "gitlab": settings.gitlab_token,
        "bitbucket": settings.bitbucket_token,
        "gitea": settings.gitea_token,
    }


def forge_name_for_url(url: str, override: str | None = None) -> str:
    if override:
        if override not in FORGES:
            raise ValueError(f"unknown forge: {override}")
        return override
    host = urlparse(url).netloc.lower()
    if host in KNOWN_HOSTS:
        return KNOWN_HOSTS[host]
    for name, base in (("gitlab", settings.gitlab_url), ("gitea", settings.gitea_url)):
        if host == urlparse(base).netloc:
            return name
    raise ValueError(f"unknown forge host: {host}. pass forge explicitly for self-hosted instances.")


def forge_for_url(url: str, token: str | None = None, override: str | None = None, transport=None):
    """an adapter for the repo's forge. token priority is handled by the
    caller (the account resolver); this stays a pure constructor."""
    name = forge_name_for_url(url, override)
    return FORGES[name](token=token, transport=transport)
