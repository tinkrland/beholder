"""the bitbucket forge adapter. rest api, no clone, read-only. same protocol:
list_refs, list_tree (with the ref's commit sha attached), fetch_blob."""

from typing import Any

import httpx


class BitbucketForge:
    API = "https://api.bitbucket.org/2.0"

    def __init__(self, token: str | None = None, transport: httpx.BaseTransport | None = None):
        # bitbucket cloud basic auth over api keys: {username}:{app_password}
        self.headers = {"authorization": f"Basic {token}"} if token else {}
        self.transport = transport  # tests inject a mock transport; prod never does

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.API, headers=self.headers, timeout=30, transport=self.transport)

    def list_refs(self, repo: str) -> list[str]:
        with self._client() as c:
            branches = c.get(f"/repositories/{repo}/refs/branches", params={"pagelen": 100})
            branches.raise_for_status()
            tags = c.get(f"/repositories/{repo}/refs/tags", params={"pagelen": 100})
            tags.raise_for_status()
        return [b["name"] for b in branches.json()["values"]] + [t["name"] for t in tags.json()["values"]]

    def list_tree(self, repo: str, ref: str) -> list[dict[str, Any]]:
        with self._client() as c:
            commit = c.get(f"/repositories/{repo}/commit/{ref}")
            commit.raise_for_status()
            sha = commit.json()["hash"]
            entries: list[dict] = []
            url = f"/repositories/{repo}/src/{ref}"
            while url:
                r = c.get(url, params={"pagelen": 100, "max_depth": 20, "fields": "values.path,values.size,values.type,next"})
                r.raise_for_status()
                data = r.json()
                entries.extend(data.get("values", []))
                url = data.get("next")  # bitbucket paginates with full urls
        return [{"path": e["path"], "size": e.get("size") or 0, "commit_sha": sha} for e in entries if e.get("type") == "commit_file"]

    def fetch_blob(self, repo: str, ref: str, path: str) -> dict[str, Any]:
        with self._client() as c:
            r = c.get(f"/repositories/{repo}/src/{ref}/{path}")
            r.raise_for_status()
        return {"content": r.text, "commit_sha": ""}
