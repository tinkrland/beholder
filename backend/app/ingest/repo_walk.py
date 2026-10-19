"""the rest walk: list the tree, apply excludes, fetch selected blobs, chunk
them with line ranges, redact secrets before anything else sees the text.
a map that names what it did not read comes back with the chunks."""

from .excludes import Excludes, select_tree
from .forge import forge_for_url, parse_repo_url
from .secrets import redact

CHUNK_LINES = 120


def chunk_text(text: str, path: str, sha: str | None = None, chunk_lines: int = CHUNK_LINES) -> list[dict]:
    lines = text.splitlines()
    chunks = []
    for start in range(0, len(lines), chunk_lines):
        piece = lines[start : start + chunk_lines]
        chunks.append(
            {
                "path": path,
                "text": "\n".join(piece),
                "lines_start": start + 1,
                "lines_end": start + len(piece),
                "commit_sha": sha,
            }
        )
    if not chunks:
        chunks = [{"path": path, "text": "", "lines_start": 0, "lines_end": 0, "commit_sha": sha}]
    return chunks


def walk_repo(
    repo_url: str,
    ref: str,
    forge=None,
    budget: int = 200,
    beholderignore: str | None = None,
) -> dict:
    """returns {chunks, report}. the report carries selected/skipped/unread and
    the commit sha, so every fact can cite repo, ref, path, lines, sha."""
    forge = forge or forge_for_url(repo_url)
    repo = "/".join(parse_repo_url(repo_url))
    tree = forge.list_tree(repo, ref)
    paths = [e["path"] for e in tree]
    sha = tree[0]["commit_sha"] if tree else None

    excludes = Excludes(beholderignore)
    selected, report = select_tree(paths, excludes, budget=budget)

    # the walk's own ignore file, if present, refines the walk after the first pass
    ignore_path = next((p for p in selected if p.rsplit("/", 1)[-1] == ".beholderignore"), None)
    if ignore_path:
        blob = forge.fetch_blob(repo, ref, ignore_path)
        excludes = Excludes(blob["content"])
        selected, report = select_tree(paths, excludes, budget=budget)

    chunks: list[dict] = []
    for path in selected:
        entry = next(e for e in tree if e["path"] == path)
        if entry.get("size", 0) > 512_000:  # 500kb blobs are skipped, reported, not failed
            report["unread_budget"] = report.get("unread_budget", []) + [path]
            continue
        blob = forge.fetch_blob(repo, ref, path)
        text, had_secrets = redact(blob["content"])
        for c in chunk_text(text, path, sha):
            c["redacted"] = had_secrets
            chunks.append(c)

    report["commit_sha"] = sha
    report["repo"] = repo
    report["ref"] = ref
    return {"chunks": chunks, "report": report}
