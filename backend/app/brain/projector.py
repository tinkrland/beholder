"""the projector: project(model_version, lens) -> pitch_view. nine fixed
sections, every sentence bound to facts or lens criteria, unbound sentences
dropped at render, low-confidence bindings flagged for confirmation."""

import hashlib

from ..schemas import FactOut, LensOut, PitchViewOut, Section, Sentence
from .retrieval import relevant_facts, render_facts, resolve_fact_ids
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
    sentences: list[Sentence] = []
    section_list: list[Section] = []
    dropped: list[dict] = []
    crit_names = {c.name for c in lens.criteria}

    for skey in _SECTION_ORDER:
        # each section sees only facts ranked relevant to its theme. one
        # call per section with the whole corpus makes a thinking model
        # outrun gateway timeouts and adds noise, not evidence.
        theme = _SECTION_THEMES.get(skey, skey)
        sel = relevant_facts(f"{theme} {' '.join(lens.vocabulary)} {lens.alternatives_frame or ''}", facts, lens, limit=32)
        out = await run(
            "generate_view",
            {"section_key": skey, "lens": lens_blob, "facts": render_facts(sel)},
        )
        texts = [str(t).strip() for t in out.get("sentences", []) if str(t).strip()]
        if not texts:
            section_list.append(Section(key=skey, sentence_ids=[]))
            continue

        # binding runs per section too, against the same slice the section
        # was written from: a sentence can only rest on evidence its
        # section actually had. one giant bind over the whole corpus was
        # the slowest call in the pipeline and the first to outrun the
        # gateway proxy.
        bind_out = await run(
            "bind_sentences",
            {
                "criteria": "\n".join(c.name for c in lens.criteria),
                "facts": render_facts(sel),
                "sentences": "\n".join(f"{i}: {s}" for i, s in enumerate(texts)),
            },
        )
        bound_by_index = {b.get("index"): b for b in bind_out.get("bindings", [])}

        sids: list[str] = []
        for i, text in enumerate(texts):
            b = bound_by_index.get(i, {})
            fact_ids_bound = resolve_fact_ids(b.get("fact_ids", []), sel)
            crit_ids = [c for c in b.get("criterion_ids", []) if c in crit_names]
            if not fact_ids_bound and not crit_ids:
                dropped.append({"section": skey, "text": text, "reason": "unbound"})
                continue
            needs_confirmation = any(
                fact_ids_bound and f.status != "confirmed" and f.confidence < CONFIRM_THRESHOLD
                for f in (fact_ids.get(fid) for fid in fact_ids_bound)
                if f
            )
            sid = f"{skey}:{len(all_sentences)}"
            all_sentences.append(text)
            sentences.append(
                Sentence(
                    id=sid,
                    text=text,
                    fact_ids=fact_ids_bound,
                    criterion_ids=crit_ids,
                    needs_confirmation=needs_confirmation,
                )
            )
            sids.append(sid)
        section_list.append(Section(key=skey, sentence_ids=sids))

    kept_sections = section_list
    kept_ids = {s.id for s in sentences}

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


_SECTION_THEMES = {
    "one_liner": "what the project is, core capability, what it does",
    "category_frame": "category, platform, market, positioning",
    "problem_as_they_see_it": "user, problem, pain, audience",
    "alternatives": "alternative, existing tools, comparison, without this",
    "what_is_different": "differentiator, unique, mechanic, approach",
    "proof": "demo, test, maturity, metric, working, shipped",
    "objections_and_honest_answers": "constraint, limitation, roadmap, honest",
    "what_not_to_lead_with": "weakness, unproven, unsupported, not ready",
    "gaps": "missing, absent, unknown, not yet, no evidence",
}

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
