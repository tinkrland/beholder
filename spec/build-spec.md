# beholder build spec

## 0. what we are building

beholder takes a project (repo, url, docs, or pasted text) and one or more targets (an uploaded rubric, a preset, or a custom brief), and produces scored, evidence-bound pitches per target, plus gaps and overclaim fixes. later, it recommends which targets to pitch at.

the target is the unit. v1 is for projects with code, full or half written: repos are the primary input. positioning and pitching only: no campaign, posting, scheduling, ads, seo, or brand features. no dependency on any other tool.

beholder runs as a hosted service and is self-hostable. the source is available; open-sourcing depends.

## 1. architecture

```
project inputs (text, docs, repo, url)
   → ingest
   → extraction (facts + provenance)
   → project model (versioned facts graph)
                    │
target inputs (rubric upload, preset, custom)
   → lens builder (parse, review, version)
                    │
                    ▼
          scorer · gap finder · overclaim finder
                    │
                    ▼
          projector (pitch view, sentence binding)
                    │
                    ▼
          checks (honesty, consistency)
                    │
                    ▼
          exporter (formats)
                    │
                    ▼
          web app (fact editor, lens review, switcher)
```

services:

- **web app:** ui and sessions
- **api:** projects, facts, lenses, views, checks, exports
- **ingest workers:** document parsing, repo snapshots, url fetch
- **extraction workers:** produce facts with provenance
- **lens builder:** rubric parsing, preset management, custom lens drafting
- **scorer:** per-criterion scoring, gap and overclaim detection
- **projector:** renders pitch views with sentence binding
- **checker:** honesty and consistency
- **exporter:** format templates
- **llm gateway:** single place for all model calls, schemas, caching, cost
- **billing service:** plans, limits, metering

## 2. accounts and projects

- sign in with email magic link and github
- `user { id, email, github_id?, plan, created_at }`
- `project { id, owner_id, name, settings, created_at }`
- solo-first. `owner_id` sits behind a membership table so teams can be added without migration.

## 3. ingest

inputs per project, any combination:

- repos: github first, then gitlab, bitbucket, and gitea. public via url; private via a connected account or url plus token. all forges behind one adapter interface: list refs, list tree, fetch blob
- a project can attach several repos (main, site, api split), each with its own ref or branch
- pasted text
- uploaded files: pdf, docx, md, txt, json (text extraction; ocr for scanned pdf later)
- doc-site urls: gitbook, quartz, and similar wikis, crawled within the site root with a page budget
- live url scrape

repo handling:

- rest walk over the forge's api, not a clone: list the tree, apply excludes, fetch selected blobs. a shallow clone into a network-restricted sandbox is the later upgrade for depth
- respect `.beholderignore`; default excludes: dependency folders, build output, binaries, media, env files, secret patterns
- size limits per plan
- secret scanning and redaction before any content reaches an llm
- facts cite repo, ref, path, and lines, with the commit sha recorded

output: `source { id, project_id, kind: repo | doc | url | text, forge?, ref, content_hash, created_at }` plus extracted text chunks.

## 4. extraction

three passes, all emitting facts:

1. **static:** manifests, configs, dependency lists, pricing pages, metadata (repo inputs)
2. **structural:** routes, flows, features, onboarding (repo inputs)
3. **semantic:** llm reads chunked sources (docs, readme, pasted text) and proposes facts: capabilities, audience, differentiators, alternatives, constraints, maturity, metrics

rules:

- every fact carries provenance (path and lines, doc and page, or `user`) and a confidence score
- a fact with no provenance and not user-stated is not stored
- user-stated facts use provenance type `user`, are shown as such, and carry lower default trust
- user-confirmed facts outrank inferred facts on re-extraction; rejected facts stay rejected unless provenance changes

## 5. data model

```
fact {
  id, project_id
  kind: capability | audience | pricing | platform | mechanic | maturity
        | differentiator | alternative | constraint | metric
  statement: string
  value: json?
  provenance: [{ type: file|doc|url|user, ref, lines?, page?, commit_sha? }]
  confidence: 0..1
  status: inferred | confirmed | rejected
  content_hash
  updated_at
}

model_version {
  id, project_id, parent_id?
  fact_ids: [fact_id]
  source_hashes
  created_at
}                                   // immutable; diffable

lens {
  id, owner_id?, type: rubric | preset | custom
  name, version
  criteria: [{ name, weight, description, strong_answer, subjective? }]
  required_questions: [string]
  impresses: [string]
  red_flags: [string]
  alternatives_frame: string
  trusted_evidence: [evidence_kind]
  objection_seeds: [string]
  vocabulary: [string]
  output_formats: [format_id]
  sources: [{ type, ref }]
  last_verified: date
  staleness_days: int
  visibility: private | shared
}

target {
  id, project_id, lens_id, lens_version
  label                             // e.g. "hackathon x, sponsor track y"
  deadline?
}

score {
  id, target_id, model_version_id
  per_criterion: [{
    criterion, score: 0..5, range?: [lo, hi],
    reasoning, fact_ids: [fact_id], raise_by: string
  }]
  weighted_total, confidence
}

gap { id, target_id, criterion, weight, missing: string, would_close: string }

claim_check {                       // user's own pitch text
  id, target_id, claim_text,
  verdict: supported | partial | unsupported | contradicted,
  fact_ids, suggested_rewrite
}

pitch_view {
  id, target_id, model_version_id, lens_version
  sections: [{ key, sentence_ids }]
  sentences: [{ id, text, fact_ids, criterion_ids }]
  annotations: [{ sentence_id, override_text, pinned_fact_hashes }]
  stale: boolean
  cache_key
}

export { id, view_id, format_id, created_at, confirmed_unsupported: [fact_id] }
```

cache key = hash(relevant fact hashes + lens version + format version + prompt version).

## 6. lens builder

### rubric ingestion

1. parse upload (pdf, docx, url) to text with structure (headings, tables)
2. llm extracts criteria, weights, required questions, stated priorities with structured output
3. weights not stated: propose weights, mark as `inferred`
4. **review step is mandatory**: user confirms or edits criteria and weights before the first score
5. save as a private lens with source reference

### presets

- authored from public criteria and writing, with source urls
- each has `last_verified` and `staleness_days`; past the threshold the ui shows a warning and the lens is excluded from "recommended"
- maintained by a refresh job that diffs sources and flags changes for human review
- never claims to predict decisions

### custom

plain-language description or pasted brief → llm drafts a lens → user edits fields.

## 7. scoring and checks

### scorer

for each criterion in the lens:

1. retrieve facts relevant to the criterion
2. score 0 to 5 using the lens's `strong_answer` and `trusted_evidence` ranking; a fact from a more-trusted evidence kind counts for more
3. no supporting fact → score 0, create a gap
4. `subjective: true` criteria return a range
5. output reasoning, supporting fact ids, and `raise_by` (what evidence would raise it)

weighted total = sum(weight × score); report with a confidence level driven by fact confidence and evidence kinds.

### gap finder

gaps = criteria with low support, sorted by weight × missing score. each gap includes what would close it.

### overclaim finder

input: the user's own pitch text (optional). steps:

1. split into atomic claims
2. match each to facts
3. verdict: supported / partial / unsupported / contradicted
4. for non-supported claims, suggest a rewrite that the facts do support

### honesty guard

- every sentence in a view binds to at least one fact about the project, or to a lens criterion (for sentences about the audience, such as objections and alternatives)
- unbound sentences fail the render and are regenerated or dropped
- sentences bound to low-confidence unconfirmed facts are marked; export is blocked until the user confirms them
- the system never creates evidence: it can only point to a gap

### consistency check (stage 3)

compare sentences across views that bind to the same or opposing facts. rules for structured values (pricing, availability); llm judge for framing. output: conflict pairs and a framing that holds in every view. warns on export.

## 8. projection

`project(model_version, lens) → pitch_view`

1. **select:** weight facts by relevance to criteria
2. **suppress:** facts that hurt or distract for this reader go to "what not to lead with"
3. **rank proof:** order by the lens's `trusted_evidence`
4. **frame:** category and alternatives from the lens
5. **generate:** fill the nine sections using structured llm output
6. **bind:** each sentence lists its fact ids and criterion ids
7. **validate:** run the honesty guard

fixed sections: one-liner, category frame, problem as they see it, alternatives, what is different and why they care, proof, objections and honest answers, what not to lead with, gaps.

## 9. associativity (kept simple)

- dependency chain: `pitch_view → sentence → fact`
- a fact edit marks bound sentences stale, then their views stale
- regen rebuilds only stale sections
- annotations store the hashes of the facts they were pinned to; if those change, the annotation is kept and flagged for review, never silently dropped
- each fact edit or re-sync shows a change summary: facts that moved, views and scores affected

## 10. formats and exports

all exports are generated from a view and cannot be edited separately.

- 30-second pitch
- written application answers mapped to the rubric's required questions
- markdown and pdf brief
- later: 2-minute demo script, deck outline, partner one-pager

export is blocked on honesty failures, and warns on consistency conflicts.

## 11. matching (stage 4)

1. rank targets the user uploads by weighted fit score
2. recommend from the library using fit scores and eligibility rules
3. discovery of newly opened calls

needs a maintained `call` table: name, source, deadline, eligibility, lens link, last_verified. refresh job plus human review. eligibility mismatches are shown as reasons, not hidden.

## 12. web app

- **onboarding:** add project → review facts → add target → score
- **fact editor:** grouped by kind; confirm, reject, edit, add; provenance inline
- **lens review:** parsed criteria and weights, editable, with source highlights
- **scoreboard:** per target, per criterion; gaps ranked
- **pitch view:** single and side by side (two to four), section-aligned
- **checks panel:** overclaims, honesty flags, conflicts
- **exports:** pick view and format; download
- **history:** model versions and diffs (stage 3)

## 13. api

```
post   /projects
get    /projects/:id
post   /projects/:id/sources          upload / paste / connect repo
post   /projects/:id/extract          job
get    /projects/:id/model?version=
get    /projects/:id/model/diff?a=&b=
post   /projects/:id/facts            user-added fact
patch  /facts/:id                     confirm / reject / edit
post   /lenses                        custom or rubric upload
get    /lenses?type=preset
patch  /lenses/:id                    edit parsed criteria
post   /projects/:id/targets          { lens_id, label, deadline? }
post   /targets/:id/score             job
get    /targets/:id/gaps
post   /targets/:id/claims/check      { pitch_text }
post   /targets/:id/render            job → pitch_view
get    /views/:id
patch  /views/:id/annotations
get    /projects/:id/checks
post   /exports                       { view_id, format_id }
post   /webhooks/github
post   /webhooks/billing
```

long-running work returns a job id; the client subscribes over server-sent events.

## 14. llm orchestration

- all calls go through the llm gateway
- every call uses a json schema for structured output; invalid output is retried with the validation error, then failed
- prompts are versioned files; each stored output records prompt id and version
- routing: small models for classification and static help; stronger models for semantic extraction, rubric parsing, scoring, projection, and consistency judging
- caching keyed on prompt version + input hashes
- retrieval over chunk embeddings so context contains only relevant facts and chunks
- per-project token and cost tracking feeding billing

## 15. quality and evals

- **golden projects:** a fixed set of real and synthetic projects (repo and non-repo) with hand-labelled facts
- **golden rubrics:** a fixed set of real rubrics with hand-labelled criteria and weights
- metrics per release:
  - fact precision and recall
  - rubric parse accuracy (criteria and weights)
  - sentence binding rate (target 100 percent)
  - overclaim recall on seeded overclaims
  - score agreement with human graders on sample applications
- prompt, detector, or lens-parser changes run evals in ci and block on regressions
- in-app feedback per sentence and per score (accurate, wrong, off-angle) feeds the eval set

## 16. security and privacy

- read-only repo access by default
- ephemeral sandboxes for clones; only facts, provenance pointers, and embeddings persist
- secret scanning and redaction before any llm call
- no training on customer data; zero-retention provider configurations where available
- encryption at rest and in transit
- uploaded rubrics and applications are private; sharing is opt-in and public-only
- deletion on disconnect, project deletion, or account deletion
- audit log of access and exports

## 17. billing and limits

pricing is open. the system supports any of these without rework:

- metered units: projects, targets, scores, renders, rubric uploads
- limits enforced in the api, with soft warnings before hard stops
- usage from the llm gateway and job system
- free tier: one project, a small number of targets

## 18. stack (suggestions only)

- typescript end to end; next.js web app
- postgres for core data; pgvector for chunk embeddings
- durable job queue for ingest, extraction, scoring, render
- sandboxed container workers for repo clones
- object storage for uploads and exports
- separate staging and production; preview deploys per pull request
- structured logs, traces across api → job → llm gateway; dashboards for latency, failures, token spend, time to first score

## 19. testing

- unit tests for extractors against fixture sources
- schema tests for every llm output type
- rubric parser tests on golden rubrics
- integration tests for the full pipeline on golden projects
- regen tests: apply a scripted fact edit and assert exactly the expected views go stale and rebuild
- end-to-end ui tests for onboarding, lens review, comparison, and export

## 20. build order

1. accounts, project inputs (text, docs, repo), ingest, extraction, fact editor
2. llm gateway, model versioning
3. rubric ingestion, parse review, lens store
4. scorer and gap finder
5. projector with sentence binding; 30-second pitch and application answers
6. honesty guard and overclaim finder
7. preset lenses (yc, emergent ventures) with staleness handling; custom lenses
8. side-by-side comparison and consistency check
9. evals in ci, billing and limits
10. fact-edit regen, repo re-sync, change summaries
11. matching

rubric first: the rubric is explicit, so anyone can check whether the scoring makes sense. that is the tightest feedback loop for the whole product.

## 21. invariants

- one project model per project; views are projections, never sources
- every fact has provenance or is labeled user-stated
- every sentence binds to a fact about the project or to a lens criterion
- view edits are annotations or fact edits, nothing else
- fact changes propagate to every bound view
- beholder never invents evidence to close a gap
- preset lenses are never presented as current past their staleness threshold
- export is blocked on honesty failures
- positioning and pitching only

## 22. open questions

- pricing: per project, per target, or subscription
- how to refresh preset lenses and the calls database cost-effectively
- how to score subjective criteria fairly
- how much of the lens library is shared versus private
- how to handle targets that publish no criteria
- whether a "simulate the reader" feature stays within pitching
