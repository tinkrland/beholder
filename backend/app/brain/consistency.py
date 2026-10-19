"""the cross-view consistency check: one project, many readers, one story. a
sentence shown to one target's view is compared against sentences shown to
another target's view, because the project model is one even when the framing
is not. the pairing is deterministic and capped fairly; the verdicts are the
model's; contradictions are reported, never rewritten automatically: deciding
which front to correct is the owner's call, not the tool's."""

VERDICTS = ("consistent", "contradiction", "unrelated")


def view_sentences(view: dict) -> list[str]:
    """reader-facing text from a stored view. sentences only: section titles
    and structure are framing, not claims. stored views carry sentence dicts;
    already-normalized views carry strings. idempotent by design."""
    out = []
    for s in view.get("sentences", []):
        text = s.strip() if isinstance(s, str) else (s.get("text", "").strip() if isinstance(s, dict) else "")
        if text:
            out.append(text)
    return out


def cross_view_pairs(views: list[dict], max_pairs: int = 40) -> list[dict]:
    """every sentence pair from different views. identical sentences are
    agreement, not contradiction: deduped and counted, never sent. the cap
    round-robins over views so a long view cannot crowd out the rest.

    pair order is deterministic: sorted by (i, j), so the same views always
    produce the same pairs in the same order.
    """
    views = [{**v, "sentences": view_sentences(v)} for v in views]  # strings from here on
    pairs: list[tuple[int, int, int, int]] = []  # (i_sent, j_sent, i_view, j_view)
    for i, vi in enumerate(views):
        for j, vj in enumerate(views):
            if i >= j:
                continue  # each view pair once, no self pairs
            si, sj = vi["sentences"], vj["sentences"]
            for a in range(len(si)):
                for b in range(len(sj)):
                    pairs.append((a, b, i, j))
    # identical text across two views is agreement, not contradiction
    deduped = []
    echoes = 0
    for a, b, i, j in pairs:
        if views[i]["sentences"][a] == views[j]["sentences"][b]:
            echoes += 1
            continue
        deduped.append((a, b, i, j))
    # round-robin cap: cycle through view pairs so no pair of views hogs the budget
    if len(deduped) > max_pairs:
        by_view_pair: dict[tuple[int, int], list] = {}
        for p in deduped:
            by_view_pair.setdefault((p[2], p[3]), []).append(p)
        capped, cursor = [], 0
        while len(capped) < max_pairs and any(by_view_pair.values()):
            for key in sorted(by_view_pair):
                bucket = by_view_pair[key]
                if bucket and len(capped) < max_pairs:
                    capped.append(bucket.pop(0))
        deduped = sorted(capped, key=lambda p: (p[2], p[3], p[0], p[1]))
    return {
        "pairs": [
            {"a": {"view": i, "index": a, "text": views[i]["sentences"][a]},
             "b": {"view": j, "index": b, "text": views[j]["sentences"][b]}}
            for a, b, i, j in deduped
        ],
        "echoes": echoes,  # identical sentences across views: agreement, counted
    }


async def check_consistency(views: list[dict], run, max_pairs: int = 40) -> dict:
    """views in, contradictions out. one model call carries the capped pair
    list; verdicts outside the allowed set are 'unrelated' so a sloppy model
    can only underreport, never invent. nothing is rewritten here."""
    for v in views:
        v["sentences"] = view_sentences(v)
    if len(views) < 2 or not any(v["sentences"] for v in views):
        return {
            "checked_views": [{"label": v.get("label", ""), "target_id": v.get("target_id", ""), "sentence_count": len(v["sentences"])} for v in views],
            "pairs_checked": 0,
            "echoes": 0,
            "contradictions": [],
            "consistent": True,
            "note": "fewer than two views with sentences: nothing to compare",
        }
    built = cross_view_pairs(views, max_pairs)
    pairs = built["pairs"]
    labels = {i: v.get("label", f"view {i}") for i, v in enumerate(views)}
    out = await run(
        "check_consistency",
        {
            "views": "\n".join(f"{i}: {labels[i]}" for i in labels),
            "pairs": "\n".join(f"{i}: [a] {p['a']['text']} [b] {p['b']['text']}" for i, p in enumerate(pairs)),
        },
    )
    raw = out.get("verdicts", [])
    verdicts = []
    for i, p in enumerate(pairs):
        v = raw[i].get("verdict", "unrelated") if i < len(raw) and isinstance(raw[i], dict) else "unrelated"
        if v not in VERDICTS:
            v = "unrelated"
        verdicts.append(v)
    contradictions = [
        {
            "a": {"target_id": views[p["a"]["view"]].get("target_id", ""), "label": labels[p["a"]["view"]], "sentence": p["a"]["text"]},
            "b": {"target_id": views[p["b"]["view"]].get("target_id", ""), "label": labels[p["b"]["view"]], "sentence": p["b"]["text"]},
            "explanation": (raw[i].get("explanation") if i < len(raw) and isinstance(raw[i], dict) else None) or "the two views make claims that cannot both be true",
        }
        for i, p in enumerate(pairs)
        if verdicts[i] == "contradiction"
    ]
    return {
        "checked_views": [{"label": v.get("label", ""), "target_id": v.get("target_id", ""), "sentence_count": len(v["sentences"])} for v in views],
        "pairs_checked": len(pairs),
        "echoes": built["echoes"],
        "contradictions": contradictions,
        "consistent": not contradictions,
    }
