"""the gitea forge adapter. rest api, no clone, read-only. same protocol:
list_refs, list_tree (with the ref's commit sha attached), fetch_blob.
gitea is usually self-hosted: BEHOLDER_GITEA_URL points at the instance."""

from typing import Any

import httpx

from ..config import settings


class GiteaForge:
    API = settings.gitea_url  # default https://gitea.com/api/v1, overridable

    def __init__(self, token: str | None = None, transport: httpx.BaseTransport | None = None):
        self.headers = {"authorization": f"token {token}"} if token else {}
        self.transport = transport  # tests inject a mock transport; prod never does

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.API, headers=self.headers, timeout=30, transport=self.transport)

    def list_refs(self, repo: str) -> list[str]:
        with self._client() as c:
            branches = c.get(f"/repos/{repo}/branches")
            branches.raise_for_status()
            tags = c.get(f"/repos/{repo}/tags")
            tags.raise_for_status()
        return [b["name"] for b in branches.json()] + [t["name"] for t in tags.json()]

    def list_tree(self, repo: str, ref: str) -> list[dict[str, Any]]:
        with self._client() as c:
            commit = c.get(f"/repos/{repo}/git/commits/{ref}")
            commit.raise_for_status()
            sha = commit.json()["sha"]
            entries: list[dict] = []
            page = 1
            while True:
                r = c.get(f"/repos/{repo}/git/trees/{sha}", params={"recursive": "true", "per_page": 100, "page": page})
                r.raise_for_status()
                batch = r.json().get("entries", [])
                entries.extend(batch)
                if r.json().get("truncated") is not True and len(batch) < 100:
                    break
                page += 1
                if not batch:
                    break
        return [{"path": e["path"], "size": e.get("size") or 0, "commit_sha": sha} for e in entries if e.get("type") == "blob"]

    def fetch_blob(self, repo: str, ref: str, path: str) -> dict[str, Any]:
        with self._client() as c:
            r = c.get(f"/repos/{repo}/raw/{path}", params={"ref": ref})
            r.raise_for_status()
        return {"content": r.text, "commit_sha": ""}
