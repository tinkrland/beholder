"""the projector: project(model_version, lens) -> pitch_view. nine fixed
sections, every sentence bound to facts or lens criteria, unbound sentences
dropped at render, low-confidence bindings flagged for confirmation."""

import hashlib

from ..schemas import FactOut, LensOut, PitchViewOut, Section, Sentence
from .retrieval import relevant_facts, render_facts
from .honesty import CONFIRM_THRESHOLD


def _cache_key(facts: list[FactOut], lens_version: int) -> str:
    blob = "|".join(sorted(f"{f.id}:{f.content_hash}" for f in facts)) + f"|lens v{lens_version}"
    return hashlib.sha256(blob.encode()).hexdigest()


async def project(target_id: str, model_version_id: str, facts: list[FactOut], lens: LensOut, run) -> PitchViewOut:
    """generates the nine sections, binds every sentence, drops unbound ones.
    a view that comes out of here has passed the bind check by construction;
    the honesty guard still decides export on fact confirmation status."""
    key = _cache_key(facts, lens.version)
    lens_blob = (
        f"name: {lens.name}\nalternatives: {lens.alternatives_frame}\n"
        f"impresses: {lens.impresses}\nred flags: {lens.red_flags}\n"
        f"vocabulary: {lens.vocabulary}\nobjections: {lens.objection_seeds}"
    )
    fact_ids = {f.id: f for f in facts}

    all_sentences: list[str] = []
    section_list: list[Section] = []
    dropped: list[dict] = []

    for skey in _SECTION_ORDER:
        out = await run(
            "generate_view",
            {"section_key": skey, "lens": lens_blob, "facts": render_facts(facts)},
        )
        sids: list[str] = []
        for text in out.get("sentences", []):
            text = str(text).strip()
            if not text:
                continue
            all_sentences.append(text)
            sids.append(f"{skey}:{len(all_sentences) - 1}")
        section_list.append(Section(key=skey, sentence_ids=sids))

    # one binding pass over every sentence
    bindings = await run(
        "bind_sentences",
        {
            "criteria": "\n".join(c.name for c in lens.criteria),
            "facts": render_facts(facts),
            "sentences": "\n".join(f"{i}: {s}" for i, s in enumerate(all_sentences)),
        },
    )
    bound_by_index = {b.get("index"): b for b in bindings.get("bindings", [])}

    sentences: list[Sentence] = []
    kept_sections: list[Section] = []
    kept_ids = set()
    for section in section_list:
        sids = []
        for sid in section.sentence_ids:
            _, idx = sid.split(":", 1)
            idx = int(idx)
            b = bound_by_index.get(idx, {})
            fact_ids_bound = [f for f in b.get("fact_ids", []) if f in fact_ids]
            crit_ids = [c for c in b.get("criterion_ids", []) if c in {x.name for x in lens.criteria}]
            if not fact_ids_bound and not crit_ids:
                dropped.append({"section": section.key, "text": all_sentences[idx], "reason": "unbound"})
                continue
            needs_confirmation = any(
                fact_ids_bound and f.status != "confirmed" and f.confidence < CONFIRM_THRESHOLD
                for f in (fact_ids.get(fid) for fid in fact_ids_bound)
                if f
            )
            sentences.append(
                Sentence(
                    id=sid,
                    text=all_sentences[idx],
                    fact_ids=fact_ids_bound,
                    criterion_ids=crit_ids,
                    needs_confirmation=needs_confirmation,
                )
            )
            sids.append(sid)
            kept_ids.add(sid)
        kept_sections.append(Section(key=section.key, sentence_ids=sids))

    view = PitchViewOut(
        id="",
        target_id=target_id,
        model_version_id=model_version_id,
        lens_version=lens.version,
        sections=kept_sections,
        sentences=sentences,
        stale=False,
        cache_key=key,
    )
    # dropped sentences travel as annotations: nothing is silently lost
    if dropped:
        view.annotations = [{"type": "dropped", "items": dropped}]  # type: ignore[attr-defined]
    return view


_SECTION_ORDER = [
    "one_liner",
    "category_frame",
    "problem_as_they_see_it",
    "alternatives",
    "what_is_different",
    "proof",
    "objections_and_honest_answers",
    "what_not_to_lead_with",
    "gaps",
]
