# roadmap

## stage 1: rubric to score (core loop)

- project input from pasted text, docs, or a repo
- fact extraction with provenance, fact editor
- rubric upload, parsing, review step, lens
- scoring against a lens, gap finder
- 30-second pitch and application answers
- exit test: a user uploads a real hackathon rubric and agrees the scores and gaps make sense

## stage 2: honesty and presets

- pitch view with nine sections
- honesty guard, overclaim finder
- preset lenses (yc, emergent ventures) with sources and last-verified dates
- custom lenses
- side-by-side comparison of up to four targets
- exit test: users fix at least one overclaim per project and report using an export in a real application

## stage 3: consistency and iteration

- consistency check across targets (done, oct 19 2026)
- edit a fact, see scores and gaps update (done, oct 20 2026: POST /projects/{id}/facts, PUT /facts/{id}, POST /facts/{id}/review; fact changes flag views stale, rejected facts never feed the model)
- model versioning and diff (done, oct 20 2026: GET /projects/{id}/model-versions lists the snapshots, diff compares by content hash so re-derived facts are not churn, review actions show as status changes)
- repo re-sync with change summaries (done, oct 20 2026: POST /sources/{id}/resync, insert-only source history, per-file diff in meta.change_summary)
- more formats: demo script, deck outline, partner one-pager

## stage 4: matching

- rank the scored targets by fit (done, oct 20 2026: GET /projects/{id}/matching, fit comes only from scores on the table)
- suggest library presets by readiness (done: criteria x grounding, silence named, no invented fit)
- discovery of newly opened calls that fit (open)
- requires a maintained database of calls, deadlines, and eligibility (open)

## stage 5: library network effects

- opt-in contribution of public rubrics to the shared library
- reviewed community lenses
- outcome reporting (advanced, funded) to calibrate lens quality

## deliberately not on the roadmap

marketing features of any kind, integrations that turn beholder into a publishing tool, and guarantees of outcomes.
