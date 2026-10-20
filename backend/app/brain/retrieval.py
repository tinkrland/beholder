"""fact retrieval. deterministic, no embeddings: keyword overlap plus the lens's
trusted_evidence ranking. good enough for mvp, swappable later behind the same
signature."""

from ..schemas import FactOut, LensOut

STOPWORDS = {
    "a", "an", "the", "of", "for", "and", "or", "to", "in", "on", "with", "is",
    "are", "be", "by", "as", "at", "that", "this", "it", "its", "their", "from",
    "how", "what", "which", "your", "you", "they", "than", "then", "can", "does",
}


def tokens(text: str) -> set[str]:
    return {t for t in "".join(c if c.isalnum() else " " for c in text.lower()).split() if t not in STOPWORDS and len(t) > 2}


def evidence_rank(fact: FactOut, lens: LensOut) -> int:
    """facts from evidence kinds this reader trusts count for more. facts whose
    provenance type is not in the list rank last, not zero: the list is a
    ranking, not a filter."""
    kind_map = {"file": "public repo with recent commits", "url": "live demo", "doc": "uploaded docs", "user": "user statement"}
    prov_type = fact.provenance[0].type if fact.provenance else "user"
    kind = kind_map.get(prov_type, prov_type)
    for i, trusted in enumerate(lens.trusted_evidence):
        if trusted.lower() in kind or kind in trusted.lower():
            return i
    return len(lens.trusted_evidence) + 1


def relevant_facts(criterion_text: str, facts: list[FactOut], lens: LensOut, limit: int = 12) -> list[FactOut]:
    """facts ranked by relevance to the criterion, then by how much this reader
    trusts the evidence kind, then by confidence. rejected facts never appear."""
    want = tokens(criterion_text)
    usable = [f for f in facts if f.status != "rejected"]

    def relevance(f: FactOut) -> float:
        have = tokens(f.statement)
        overlap = len(want & have)
        return overlap / max(len(want), 1)

    ranked = sorted(
        usable,
        key=lambda f: (round(relevance(f), 2), -evidence_rank(f, lens), -f.confidence),
        reverse=True,
    )
    return ranked[:limit]


def short_id(fid: str) -> str:
    """the id a model sees and copies back: a short prefix of the fact id.
    models truncate long uuids mid-copy, silently dropping the binding."""
    return fid[:8]


def resolve_fact_ids(candidates: list, facts: list[FactOut]) -> list[str]:
    """model-returned ids are resolved back to real fact ids: exact match,
    or a unique prefix match against what the prompt actually showed. an
    ambiguous or unknown id resolves to nothing, so a sloppy model can
    only lose support, never invent it. order kept, duplicates dropped."""
    by_short: dict[str, list[str]] = {}
    known = set()
    for f in facts:
        by_short.setdefault(f.id[:8], []).append(f.id)
        known.add(f.id)
    out: list[str] = []
    for c in candidates:
        c = str(c).strip().lower()
        if not c:
            continue
        if c in known:
            fid = c
        else:
            hits = by_short.get(c[:8], [])
            fid = hits[0] if len(hits) == 1 else None
        if fid and fid not in out:
            out.append(fid)
    return out


def render_facts(facts: list[FactOut]) -> str:
    """compact, line-addressable rendering for prompts. ids are short on
    purpose: models copy short ids faithfully and truncate long uuids."""
    lines = []
    for f in facts:
        prov = f.provenance[0] if f.provenance else None
        where = f"{prov.ref}:{prov.lines[0]}" if prov and prov.lines else (prov.ref if prov else "user")
        lines.append(f"[{short_id(f.id)}] ({f.kind}, {f.status}, conf {f.confidence:.2f}, {where}) {f.statement}")
    return "\n".join(lines)
