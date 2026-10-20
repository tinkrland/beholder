"""the three extraction passes, all emitting facts with provenance.

static: manifests, configs, dependency lists, metadata. deterministic, no model.
structural: routes, flows, features from the repo shape. deterministic, no model.
semantic: the gateway reads selected chunks and proposes facts.

every fact carries provenance. a fact with no provenance and not user-stated is
not stored: the passes here cannot even express it.
"""

from typing import Any
import json

from ..schemas import FactIn, Provenance

Runner = object  # any async callable (task_id, payload) -> dict


# source priority for the semantic pass: the build order says it reads docs,
# readme, and pasted text. the user's own words are the densest signal, then
# uploaded docs, then crawled pages, then repo files (already stored with
# readme first).
SELECTION_PRIORITY = {"text": 0, "doc": 1, "url": 2, "repo": 3}


def select_semantic_chunks(chunk_rows: list[dict], max_chunks: int) -> list[dict]:
    """picks what the semantic pass reads. sources in priority order, then
    round-robin across sources of equal priority, so one long document
    cannot eat the whole budget before a second source is read at all.
    chunks stay in their stored order within a source: a repo's chunks
    are already ranked (readme first)."""
    groups: dict[int, dict[str, list[dict]]] = {}
    for row in chunk_rows:
        sid = str(row.get("source_id", ""))
        prio = SELECTION_PRIORITY.get(row.get("source_kind", "repo"), 3)
        groups.setdefault(prio, {}).setdefault(sid, []).append(row)
    picked: list[dict] = []
    for prio in sorted(groups):
        # round-robin across the sources of this priority: one chunk each
        # per turn, so no single source can eat the group's whole share
        buckets = groups[prio]
        cursor = 0
        while len(picked) < max_chunks:
            progressed = False
            for sid in sorted(buckets):
                bucket = buckets[sid]
                if cursor >= len(bucket):
                    continue
                picked.append(bucket[cursor])
                progressed = True
                if len(picked) >= max_chunks:
                    break
            if not progressed:
                break
            cursor += 1
        if len(picked) >= max_chunks:
            break
    return picked


def _prov(ref: str, lines: list[int] | None = None, sha: str | None = None, kind: str = "file") -> list[Provenance]:
    return [Provenance(type=kind, ref=ref, lines=lines, commit_sha=sha)]


def static_pass(chunks: list[dict]) -> list[FactIn]:
    """deterministic facts from manifests and configs. reads only the chunk dicts:
    {path, text, lines_start, lines_end, commit_sha}."""
    facts: list[FactIn] = []
    for c in chunks:
        path, text, sha = c["path"], c["text"], c.get("commit_sha")
        lines = [c.get("lines_start", 0), c.get("lines_end", 0)]
        name = path.rsplit("/", 1)[-1].lower()
        kind = c.get("kind", "file")

        if name == "package.json":
            try:
                pkg = json.loads(text)
            except ValueError:
                continue
            if pkg.get("name"):
                facts.append(FactIn(project_id="", kind="capability", statement=f"the project's package name is {pkg['name']}", provenance=_prov(path, lines, sha, kind), confidence=0.9))
            deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
            if deps:
                top = ", ".join(sorted(deps)[:10])
                facts.append(FactIn(project_id="", kind="platform", statement=f"built on node with {len(deps)} declared dependencies including {top}", provenance=_prov(path, lines, sha, kind), confidence=0.85))
            for dep, ver in (pkg.get("dependencies") or {}).items():
                facts.append(FactIn(project_id="", kind="constraint", statement=f"depends on {dep} ({ver})", value={"version": ver}, provenance=_prov(path, lines, sha, kind), confidence=0.8))

        elif name == "requirements.txt":
            reqs = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
            if reqs:
                facts.append(FactIn(project_id="", kind="platform", statement=f"python project with {len(reqs)} declared requirements including {', '.join(reqs[:10])}", provenance=_prov(path, lines, sha, kind), confidence=0.85))

        elif name in {"dockerfile", "containerfile"}:
            facts.append(FactIn(project_id="", kind="platform", statement="ships as a container", provenance=_prov(path, lines, sha, kind), confidence=0.9))

        elif "/.github/workflows/" in path or "/.gitlab-ci" in path:
            facts.append(FactIn(project_id="", kind="platform", statement="ci is configured in the repo", provenance=_prov(path, lines, sha, kind), confidence=0.8))

    return facts


def _normalize_value(v: Any) -> dict[str, Any] | None:
    """facts store values as objects (measure, unit, label). a model that
    returns a scalar or nothing must never crash the pass: wrap it or drop
    it, never fail the extract."""
    if isinstance(v, dict):
        return v
    if isinstance(v, (str, int, float, bool)) and str(v).strip():
        return {"value": v}
    return None


def structural_pass(paths: list[str], commit_sha: str | None = None) -> list[FactIn]:
    """features and flows read from the repo shape. observed, not verified:
    the file existing is the evidence, and that is all the confidence claimed."""
    facts: list[FactIn] = []
    p = [x.lower() for x in paths]

    def has(*needles: str) -> list[str]:
        return [x for x in p for n in needles if n in x]

    if has("/api/", "routes/", "router"):
        facts.append(FactIn(project_id="", kind="capability", statement="an api surface exists in the repo (file evidence)", provenance=_prov("repo tree"), confidence=0.6))
    if has("auth", "login", "signin"):
        facts.append(FactIn(project_id="", kind="capability", statement="an authentication flow exists in the repo (file evidence)", provenance=_prov("repo tree"), confidence=0.6))
    if has("/tests/", "_test.", "test_"):
        facts.append(FactIn(project_id="", kind="maturity", statement="tests exist in the repo (file evidence)", provenance=_prov("repo tree"), confidence=0.6))
    if has("/docs/", "readme", "/.github"):
        facts.append(FactIn(project_id="", kind="maturity", statement="documentation exists in the repo (file evidence)", provenance=_prov("repo tree"), confidence=0.6))
    if has("migrations/", "alembic", "schema"):
        facts.append(FactIn(project_id="", kind="mechanic", statement="a database schema with migrations exists (file evidence)", provenance=_prov("repo tree"), confidence=0.6))
    return facts


async def semantic_pass(chunks: list[dict], project_id: str, run: Runner, max_chunks: int = 8) -> list[FactIn]:
    """the gateway reads selected chunks and proposes facts. the model returns
    {facts: [{kind, statement, lines}]} and provenance comes from the chunk, not
    from the model: the model cannot mint provenance."""
    facts: list[FactIn] = []
    for c in chunks[:max_chunks]:
        out = await run(
            "extract_facts",
            {"ref": c["path"], "lines_start": c.get("lines_start", 0), "lines_end": c.get("lines_end", 0), "text": c["text"]},
        )
        for f in out.get("facts", []):
            lines = f.get("lines") or [c.get("lines_start", 0), c.get("lines_end", 0)]
            facts.append(
                FactIn(
                    project_id=project_id,
                    kind=f.get("kind", "capability"),
                    statement=f.get("statement", "").strip(),
                    value=_normalize_value(f.get("value")),
                    provenance=_prov(c["path"], lines, c.get("commit_sha"), c.get("kind", "file")),
                    confidence=min(0.9, 0.4 + 0.1 * len(lines or [])),
                    status="inferred",
                )
            )
    return facts
