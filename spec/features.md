# features

tags: **mvp** = in the first release, **later** = planned, **out** = never.

## inputs

- paste a description **mvp**
- upload docs, decks, notes (pdf, docx, md, txt) **mvp**
- github repo, read-only **mvp**
- live url crawl **later**
- app store or product listing url **later**
- re-sync on repo changes **later**

## project model

- facts extracted with provenance (file and lines, document and page, or user-stated) **mvp**
- confidence score per fact **mvp**
- fact editor: confirm, reject, edit, add **mvp**
- user-stated facts labeled as such and lower-trust by default **mvp**
- fact kinds: capability, audience, pricing, platform, mechanic, maturity, differentiator, alternative, constraint, metric **mvp**
- versioned model with diff between versions **mvp**: every extraction snapshots an immutable model version; GET /projects/{id}/model-versions/diff names facts added, facts removed, review actions (status changes), and sources added or removed. identity is the content hash, so re-derived facts are not churn

## targets and lenses

- rubric upload (pdf, doc, url) parsed into criteria, weights, required questions **mvp**
- parse review step before first use **mvp**
- preset lenses with sources and last-verified date (yc, emergent ventures to start) **mvp**
- custom lens from pasted brief or plain language **mvp**
- sponsor tracks as separate targets, with best-fit comparison **mvp**
- lens staleness warnings **mvp**
- shared lens library from public rubrics, opt-in **later**

## scoring and checks

- per-criterion score with reasoning and what would raise it **mvp**
- weighted total with a confidence range for subjective criteria **mvp**
- gap finder, ranked by criterion weight **mvp**
- overclaim finder on the user's own pitch text, with defensible rewrites **mvp**
- honesty guard: unsupported facts cannot be exported without user confirmation **mvp**
- consistency check across targets **later**

## the pitch view

nine fixed sections, the same for every target so views compare side by side:

1. one-liner
2. category frame
3. the problem as they see it
4. alternatives they compare against
5. what is different and why they care
6. proof
7. objections and honest answers
8. what not to lead with
9. gaps

**mvp**

## formats and exports

- 30-second pitch **mvp**
- written application answers mapped to the rubric's own fields **mvp**
- markdown and pdf brief **mvp**
- 2-minute demo script **later**
- deck outline **later**
- one-pager for partners **later**

## comparison

- side by side, two to four targets, section-aligned **mvp**
- diff mode: what changes in emphasis, proof, and objections between targets **later**
- trace: click any sentence to see its facts and evidence **later**

## iteration

- edit a fact, see scores and gaps update **mvp**: any fact change (add, edit, confirm, reject) flags the views that rested on the old fact set as stale. scores are insert-only history: the new fact set speaks on the next score, and rejected facts never feed the model again
- "what if I add a demo video" simulation **later**

## matching

- rank the scored targets by fit **mvp**: weighted total first, confidence breaks ties, the top gap rides along
- suggest library presets by readiness **mvp**: how many criteria touch dimensions the project can already speak to, which would land on silence. readiness is not fit: the honest number comes when the score runs
- surface newly opened calls that fit **later**: needs a maintained database of calls, deadlines, and eligibility

## out

ad copy, social posts, scheduling, publishing, seo, ab tests, brand identity, analytics on reach or conversion, integration with other tools.
