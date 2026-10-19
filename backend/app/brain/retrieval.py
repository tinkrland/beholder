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


def render_facts(facts: list[FactOut]) -> str:
    """compact, line-addressable rendering for prompts."""
    lines = []
    for f in facts:
        prov = f.provenance[0] if f.provenance else None
        where = f"{prov.ref}:{prov.lines[0]}" if prov and prov.lines else (prov.ref if prov else "user")
        lines.append(f"[{f.id}] ({f.kind}, {f.status}, conf {f.confidence:.2f}, {where}) {f.statement}")
    return "\n".join(lines)
