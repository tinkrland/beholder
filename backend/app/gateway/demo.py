"""the demo provider: canned, deterministic responses for every gateway task,
so a local run without model keys still exercises the whole flow. outputs are
obviously canned. this file exists for local runs and tests, never for prod
honesty: canned scores are not scores."""

import re


def demo_responder(spec, user_content: str) -> dict:
    if spec.task_id == "parse_rubric":
        return {
            "name": "demo rubric",
            "criteria": [
                {"name": "technical depth", "weight": 0.3, "description": "non-trivial engineering"},
                {"name": "demo quality", "weight": 0.3, "description": "a working demo"},
                {"name": "originality", "weight": 0.2, "subjective": True},
                {"name": "impact", "weight": 0.2},
            ],
            "required_questions": ["what problem does it solve?"],
            "impresses": ["a working demo"],
            "red_flags": ["no demo"],
            "trusted_evidence": ["public repo with recent commits"],
        }

    if spec.task_id == "extract_facts":
        return {
            "facts": [
                {"kind": "capability", "statement": "the project renders the exact product mesh deterministically (demo fact)", "lines": [1, 40]},
            ]
        }

    if spec.task_id == "score_criterion":
        criterion = user_content.split("\n", 1)[0].removeprefix("criterion: ").strip()
        fact_ids = re.findall(r"\[([0-9a-f-]+)\]", user_content)
        if criterion.startswith("technical") and fact_ids:
            return {"score": 4, "reasoning": "demo: a deterministic engine is non-trivial", "fact_ids": [fact_ids[0]], "raise_by": "demo: benchmarks"}
        return {"score": 0, "reasoning": "demo: nothing supports this", "fact_ids": [], "raise_by": "demo: a demo video"}

    if spec.task_id == "check_claims":
        return {"verdict": "partial", "fact_ids": [], "suggested_rewrite": "demo rewrite: the project renders deterministic geometry"}

    if spec.task_id == "check_consistency":
        pairs = user_content.count("[b]")
        return {"verdicts": [{"verdict": "consistent"} for _ in range(pairs)]}

    if spec.task_id == "generate_view":
        return {
            "sentences": [
                "the project renders the exact product mesh deterministically (demo).",
                "no diffusion model touches the product (demo).",
            ]
        }

    if spec.task_id == "bind_sentences":
        ids = re.findall(r"\[([0-9a-f-]+)\]", user_content)
        # one binding per sentence actually sent: the canned response
        # must round-trip the request's shape, not a fixed range
        count = len(re.findall(r"^\d+: ", user_content, re.M))
        return {
            "bindings": [
                {"index": i, "fact_ids": [ids[0]] if ids else [], "criterion_ids": []}
                for i in range(count)
            ]
        }

    if spec.task_id == "draft_lens":
        return {"name": "demo reader", "criteria": [{"name": "fit", "description": "does it fit"}], "impresses": ["honesty"]}

    raise RuntimeError(f"demo provider has no response for {spec.task_id}")
