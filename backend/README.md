# beholder backend

one fastapi service, any postgres, one model gateway. self-hostable: the
deployable unit is this service plus a postgres url, with bring-your-own model
keys.

## shape

```
app/
  main.py            the fastapi app, routes under /api
  auth.py            jwt verification against standard jwks (supabase auth)
  db.py              engine and session, jsonb on postgres, json elsewhere
  models.py          the tables, one per build-spec 5 structure
  schemas.py         the pydantic wire format
  gateway/           the only module that talks to any model
  brain/             extraction, lens building, scoring, claims, projection,
                     honesty, grounding (the nine w's coverage check), preset
                     staleness and drift, cross-view consistency. pure
                     functions, runner injected, no db, no http
  presets/           authored preset lenses, one json file per target.
                     authored means confirmed by authorship: no parse, no
                     review step. adding a preset is a data file, not code
  ingest/            forge adapters (github, gitlab, bitbucket, gitea, one
                     file each, self-hosted urls overridable), the rest walk,
                     doc-site crawls (gitbook, quartz), doc inputs (md/txt/
                     json direct, pdf/docx parsed locally with pypdf/python-docx), excludes, secret
                     redaction
  api/routes.py      thin routes: validate, call the service
  jobs.py            one queue, one worker type, job rows as progress
alembic/             migrations from day one
tests/               42 tests, no network, every model call canned
```

rules the code keeps:

- the brain is pure: every check is unit-testable with canned model outputs
- model_version, score, pitch_view, export are immutable, insert-only
- a draft lens never scores; confirmation echoes every criterion back (name and weight each) and the echo must match the lens: a review that never showed the numbers is not a review. drafts are editable via PUT /lenses/{id}; a weight the human changes stops being marked inferred
- unbound sentences fail the render; export is blocked on honesty failures
- outcomes: POST /targets/{id}/outcome (advanced, funded, rejected, withdrawn), insert-only history; GET /lenses/{id}/calibration puts observed scores next to observed outcomes with sample size stated, gated at three per group, owner only (presets pool other accounts and are refused)
- the shared library: POST /lenses/{id}/contribute (public assertion, confirmed rubric parse, never publishes by submitting), POST /lenses/{id}/library-review (deployment reviewer allowlist; a contributor never reviews their own), GET /library (approved lenses with sources). no reviewers configured approves nothing
- every project-scoped route checks membership before acting: targets, gaps, pitch, claims, exports, and jobs resolve their project and 404 for strangers, never 403
- export formats: markdown, demo script, deck outline, partner one-pager. all four render the same guarded sentences rearranged; unknown formats are a 400
- repo re-sync: POST /sources/{id}/resync re-walks a repo source, inserts a new source row (history is insert-only, old facts keep their provenance), and stores what changed in meta.change_summary (files added, removed, changed)
- model versioning: every extraction snapshots an immutable model version with a parent chain; GET /projects/{id}/model-versions/diff names what changed between two extractions (facts by content hash, review actions as status changes, sources by hash)
- fact editor over http: POST /projects/{id}/facts (user-stated, confirmed by authorship), PUT /facts/{id} (edit), POST /facts/{id}/review (confirm or reject); any fact change flags the project's views stale, rejected facts never feed the model
- provenance comes from the chunk, never from the model: repo facts cite forge, ref, and the source's commit sha, tree-level facts included, so evidence names the code that was read
- the nine w's (thewframework/) are the extraction map: grounding reports
  grounded, partial, or silent per dimension, and silence is surfaced, never
  smoothed over
- secrets are redacted before any content reaches the gateway
- the rest walk reports what it did not read, and so does the doc-site crawl:
  hard same-root boundaries, a page budget, and unread links recorded
- provenance types match the source: file for repos, doc for documents, url
  for pages; the plan fact kind stores stated futures as plans, never capabilities

## run locally

```bash
cd backend
pip install -e ".[dev]"

# no keys needed: the demo provider answers every gateway task with canned,
# clearly labeled output
BEHOLDER_DATABASE_URL="sqlite+aiosqlite:///./beholder.db" \
BEHOLDER_GATEWAY_PROVIDER=demo \
BEHOLDER_DEV_AUTH=true \
uvicorn app.main:app --reload
```

then the mvp flow over http: create a project, add a text source, extract,
parse a rubric, confirm the lens, score a target, pitch, export.

the shared library needs a reviewer: set BEHOLDER_LIBRARY_REVIEWERS to a
comma separated email allowlist. with none set, contributions wait and the
api says so: nothing is approved by accident.

## migrations

```bash
BEHOLDER_DATABASE_URL=sqlite+aiosqlite:///./beholder.db alembic upgrade head
```

any postgres works. sqlite works for dev and tests. nothing is host-specific.

## tests

```bash
python -m pytest -q
```

the gateway is mocked everywhere: brain tests run against canned runners, the
api flow test runs the whole mvp pipeline over http against temp sqlite,
including the honesty guard blocking export until facts are confirmed.

## consistency across views

one project, many readers, one story. `post /projects/{id}/consistency` takes
the latest view per target and compares reader-facing sentences across views:
a sentence shown to one reader against sentences shown to another. framing
differences are fine, claims that cannot both be true are not. pairing is
deterministic and round-robin capped so no pair of views hogs the check;
identical sentences across views count as echoes (agreement), never pairs; a
sloppy model can only underreport (unknown verdicts become unrelated, never
contradictions). contradictions come back with both sides and an explanation:
the owner decides which front to correct. nothing is rewritten automatically.

## preset lenses

authored in `app/presets/data/`, one json file per target, synced into the
lenses table at startup: a changed file is a version bump in place. presets
carry `staleness_days` and start stale on arrival (`last_verified` is null
until a refresh verifies them). the refresh fetches each preset's sources and
runs a deliberately dumb drift check on authored keywords: `last_verified` is
set only when the sources resolve and still read the same, otherwise the
preset stays stale and a human re-reads it. the refresh never rewrites
criteria. stale presets are flagged in `get /presets`, never hidden, and are
excluded from recommendation.

## connected accounts

private repos read through your own credentials, per forge: github tokens,
gitlab tokens, bitbucket app passwords, gitea tokens. one account per forge:
connecting again rotates the token, `delete /forge/accounts/{forge}` revokes
immediately (the row is deleted, not flagged). token priority is the token
passed with the request, then the connected account, then the instance env
token, then anonymous. tokens are stored server-side and never returned whole:
`get /forge/accounts` shows only a last-four hint.

## providers

- `glm`: the real provider. set `BEHOLDER_GLM_API_KEY`, optionally
  `BEHOLDER_GLM_BASE_URL` and `BEHOLDER_GLM_MODEL`
- `demo`: canned responses, no keys
- `mock`: raises unless a responder is injected, for tests

fine-tuned models slot in behind the same task ids later, with no caller
changes: the brain passes task ids, never provider names.
