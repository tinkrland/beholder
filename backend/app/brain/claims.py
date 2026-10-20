"""the overclaim finder: the user's own pitch text in, atomic claims with
verdicts and defensible rewrites out. the system never invents evidence to
close a gap: unsupported means unsupported, with a rewrite that the facts
do support."""

import re

from .retrieval import resolve_fact_ids
from ..schemas import ClaimCheckOut, FactOut
from .retrieval import render_facts


def atomic_claims(pitch_text: str) -> list[str]:
    """split a pitch into atomic claims. sentence boundaries first, then
    coordinating conjunctions that introduce a new subject claim."""
    rough = [s.strip() for s in re.split(r"(?<=[.!?])\n+|(?<=[.!?])\s+", pitch_text) if s.strip()]
    claims: list[str] = []
    for s in rough:
        parts = re.split(r"\s+[;,]?\s+(?:and|but|while)\s+", s, flags=re.IGNORECASE)
        claims.extend(p.strip() for p in parts if len(p.strip()) > 3)
    return claims


async def check_claims(pitch_text: str, facts: list[FactOut], run) -> list[ClaimCheckOut]:
    """one check per atomic claim. every non-supported claim gets a suggested
    rewrite that the facts support, or none if nothing supports the claim."""
    checks: list[ClaimCheckOut] = []
    known = facts
    for claim in atomic_claims(pitch_text):
        out = await run("check_claims", {"claim": claim, "facts": render_facts(facts)})
        verdict = out.get("verdict", "unsupported")
        if verdict not in ("supported", "partial", "unsupported", "contradicted"):
            verdict = "unsupported"
        checks.append(
            ClaimCheckOut(
                id="",
                target_id="",
                claim_text=claim,
                verdict=verdict,
                fact_ids=resolve_fact_ids(out.get("fact_ids", []), facts),
                suggested_rewrite=out.get("suggested_rewrite"),
            )
        )
    return checks
