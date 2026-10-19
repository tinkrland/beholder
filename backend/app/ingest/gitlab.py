"""the gitlab forge adapter. rest api, no clone, read-only. same protocol as
github: list_refs, list_tree (with the ref's commit sha attached), fetch_blob.
self-hosted gitlab works by pointing BEHOLDER_GITLAB_URL at it."""

from typing import Any
from urllib.parse import quote

import httpx

from ..config import settings


class GitlabForge:
    API = settings.gitlab_url  # default https://gitlab.com/api/v4, overridable

    def __init__(self, token: str | None = None, transport: httpx.BaseTransport | None = None):
        self.headers = {"private-token": token} if token else {}
        self.transport = transport  # tests inject a mock transport; prod never does

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.API, headers=self.headers, timeout=30, transport=self.transport)

    @staticmethod
    def _pid(repo: str) -> str:
        return quote(repo, safe="")

    def list_refs(self, repo: str) -> list[str]:
        pid = self._pid(repo)
        with self._client() as c:
            branches = c.get(f"/projects/{pid}/repository/branches", params={"per_page": 100})
            branches.raise_for_status()
            tags = c.get(f"/projects/{pid}/repository/tags", params={"per_page": 100})
            tags.raise_for_status()
        return [b["name"] for b in branches.json()] + [t["name"] for t in tags.json()]

    def list_tree(self, repo: str, ref: str) -> list[dict[str, Any]]:
        pid = self._pid(repo)
        with self._client() as c:
            commit = c.get(f"/projects/{pid}/repository/commits/{quote(ref, safe='')}")
            commit.raise_for_status()
            sha = commit.json()["id"]
            entries: list[dict] = []
            page = 1
            while True:
                r = c.get(f"/projects/{pid}/repository/tree", params={"ref": ref, "recursive": "true", "per_page": 100, "page": page})
                r.raise_for_status()
                batch = r.json()
                entries.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
        return [{"path": e["path"], "size": e.get("size") or 0, "commit_sha": sha} for e in entries if e.get("type") == "blob"]

    def fetch_blob(self, repo: str, ref: str, path: str) -> dict[str, Any]:
        pid = self._pid(repo)
        with self._client() as c:
            r = c.get(f"/projects/{pid}/repository/files/{quote(path, safe='')}/raw", params={"ref": ref})
            r.raise_for_status()
        return {"content": r.text, "commit_sha": ""}
