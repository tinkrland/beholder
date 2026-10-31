# beholder backend stack

## 0. what this covers

where each piece of beholder runs, which tool does which job, and the order to build it in. pairs with [build-spec.md](build-spec.md), which defines what the backend must do. this file decides where and with what.

scope: v1 is for projects with code, full or half written. repos are the primary input. pre-build projects with just specs are the v2 horizon, noted in section 9.

## 1. the portability rule

- the core is plain python and plain sql. it runs anywhere a container runs, against any postgres
- the web client is a thin, swappable client that talks to the api over https with a supabase jwt. no host, platform, or framework appears inside the core's code. the api validates everything; the client validates for feel
- supabase is hosted postgres with standard protocols. a pg_dump moves the whole system. no supabase-only features in the schema unless they are optional conveniences
- beholder is self-hostable: source available, open-sourcing depends. the deployable unit is one python service plus one postgres url, and bring-your-own model keys is supported so a self-host runs on whatever gateway keys it has

test for every design decision: could this be run by a stranger with docker and a postgres url? if not, redesign.

## 2. shape

```
web client (thin ui, sessions)
        │ https, user jwt
        ▼
python api (fastapi)
        │
        ├─ ingest        firecrawl · forge adapters · doc-site crawl · bright data fallback
        ├─ gateway        the only module that talks to models
        ├─ brain          extract · score · project · check (pure functions)
        └─ jobs          background workers, job table
        │
        ▼
supabase postgres (data, rls, auth) + supabase storage (uploads)
```

auth is supabase auth (email magic link, github oauth). the client gets a jwt, the api verifies it against supabase. the api never manages sessions itself.

## 3. tool to job map

| job | tool | why |
|---|---|---|
| web client | any thin client over https | swappable; host is an implementation detail |
| api, workers, all logic | python (fastapi) | portable, testable, no host lock-in |
| data, auth, storage | supabase postgres | plain sql, exportable, rls included |
| all model calls | glm, through the gateway | keys in hand; structured output; one place for caching, retries, cost |
| doc and url ingest | firecrawl | urls to llm-ready markdown; scrape pricing and landing pages as evidence. pdf and docx parse locally (pypdf, python-docx), no service needed |
| lens research, preset refresh | tavily | fetch a target's public criteria, essays, application pages; diff sources for staleness |
| walled or anti-bot sites | bright data | unlocker, metered fallback only when firecrawl is blocked |
| fine-tuning (later) | adaptionlabs | fact extraction and claim binding are the repetitive structured tasks worth a trained model, once a few thousand labeled runs exist |
| repo ingest pattern | tin (reference only, not in prod) | read-only evidence, path:line citations, budgeted depth, status taxonomy |

## 4. inputs

### repos (the primary input)

- github first: public via url, private via a connected account or url plus token
- gitlab, bitbucket, and gitea next, all behind one adapter interface: list refs, list tree, fetch blob. each forge is an adapter over the same three calls, so adding one is a file, not a design change
- a project can attach several repos (main, site, api split), each with its own ref or branch
- ingest is a rest walk, not a clone: fetch the tree, apply default excludes plus `.beholderignore`, fetch selected blobs: readme, manifests, configs, route files, docs first
- secret scan and redaction before any content reaches the gateway
- facts cite repo, ref, path, and lines, with the commit sha recorded
- later, for depth: shallow clone into a network-restricted container, the way tin mounts read-only snapshots. the walk stays the default; the sandbox is an upgrade, since it needs infra the walk does not

### docs and prose

- formats: pdf, docx, txt, md, json, pasted text. direct parse everywhere: pypdf and python-docx locally, no external service in the upload path; firecrawl stays for live url scraping
- doc-site urls: gitbook, quartz, and similar wikis. crawl within the site root with a page budget, store each page as a url source
- ocr for scanned pdfs later

borrowed from tin (patterns, not code):

- the repo is read-only evidence. never executed, never installed
- every fact cites file and lines. unread means unclaimed
- status taxonomy: observed, documented-not-verified, hidden-but-wired. maps to fact confidence and provenance type
- budgeted depth. a map that names what it did not read beats one that ran out of time

## 5. data layer

the build-spec section 5 structures become real sql tables, one table per structure, with alembic migrations from day one.

- `fact`, `source`, `model_version`, `lens`, `target`, `score`, `gap`, `claim_check`, `pitch_view`, `export`
- `model_version`, `score`, `pitch_view`, and `export` are immutable: insert-only, latest found by ordering, never an update
- rls on user-owned rows (projects, lenses, uploads); shared lens library rows are read-only to non-authors
- provenance is jsonb with the shapes from build-spec 4, extended for multi-repo projects: repo id, forge, ref, sha
- `source` gains `kind: repo | doc | url | text` and `forge`
- indexes that matter from the start: `fact(project_id, kind, status)`, `pitch_view(target_id, model_version_id)`

## 6. python services

one deployable service for the mvp, split later if ever:

- **api:** thin. routes to the brain, nothing else
- **gateway:** the only module that talks to any model. task ids: `extract_facts`, `parse_rubric`, `draft_lens`, `score_criterion`, `check_claims`, `generate_view`, `bind_sentences`. owns prompt versions, response schemas, caching (cache key per build-spec 5), retries, cost metering. routes per task id, so a fine-tuned adaption model slots in behind the same interface later with no caller changes
- **brain:** extraction, scoring, projection, gap and overclaim finding, honesty guard. pure functions over pydantic models, so every check is unit-testable with canned model outputs and no api calls
- **ingest:** firecrawl and bright data clients, the doc-site crawler, and the forge adapters
- **jobs:** background workers (arq or a process pool) reading a `job` table: `{ id, project_id, kind, status, payload, progress }`. retries and observability live here, not in the api

## 7. jobs

we own the runtime, so there are no execution time limits. extraction of a whole repo is one job that a worker runs to completion.

keep the job rows anyway: a job table is how users see progress, how failures resume from the last finished chunk, and how cost is attributed per project. chunking is a resume strategy, not a survival strategy.

## 8. lens research

- tavily fetches a preset target's public criteria, essays, and application pages. sources recorded with `last_verified`
- a scheduled job re-fetches sources, diffs against the stored lens, and flags changes for human review. never auto-applies
- bright data only where a source is walled

## 9. build order

1. mvp flow: a public github repo plus an uploaded rubric, lens parse with mandatory review, all three extraction passes (static, structural, semantic), per-criterion scores with gaps and overclaim fixes, pitch view with sentence binding, honesty guard blocking export
2. docs and prose inputs, plus doc-site crawls (gitbook, quartz)
3. private repos via connected accounts; multi-repo and multi-branch projects
4. gitlab, bitbucket, and gitea adapters
5. presets: authored lenses plus the refresh job
6. consistency check across views
7. matching and discovery
8. pre-build mode: projects that exist only as specs. implemented oct 31 2026. a project carries a mode, build or prebuild. in prebuild the structural pass does not run at all (there is no tree to read, and inventing one would be a lie), the semantic pass reads the spec documents with the model told this is a spec, and every fact is stored with basis claimed instead of observed, user-added facts included: authorship does not make code exist. exports open with a notice saying so. the rest of the pipeline is unchanged on purpose: a lens scores claims as claims, and the honesty guard still gates the export

each stage uses the same gateway and the same tables. nothing is thrown away.

## 10. risks and open questions

- **scoring comparability.** an llm score per criterion is a judgment wearing a number. ranges for subjective criteria (build-spec 7) help, as do pinned temperature and prompt versions. the ui should say scores are advisory, not measurements.
- **rubric parse quality.** weights are often implied, and a bad parse poisons everything downstream. the mandatory review step carries this; consider requiring explicit confirmation of inferred weights before the first render.
- **forge drift.** four forges mean four api surfaces to maintain, each with its own rate limits and tree formats. keep the adapter interface to the three calls and test each adapter against a fixture repo.
- **crawl boundaries.** a doc-site crawl that wanders outside the doc root pollutes the project model. hard site-root boundaries and a page budget, per source.
- **two surfaces to keep honest.** client and api can drift on auth and validation. rule: the api validates everything, the client validates for feel. the api is the source of truth, always.
- **tool overlap.** firecrawl everywhere first, bright data metered and logged per source, so cost is visible and the fallback is provable.
- **adaption timing.** not mvp. the trigger is a labeled dataset: once a few thousand `extract_facts` and `check_claims` runs exist with user corrections, that is the training signal, and the gateway route is already in place.
- **job sprawl.** workers plus a job table invite a poor man's celery. keep it one queue, one worker type for the mvp, and only add a second when a job genuinely needs isolation (repo ingest).
