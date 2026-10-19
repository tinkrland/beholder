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
                     honesty, grounding (the nine w's coverage check). pure
                     functions, runner injected, no db, no http
  ingest/            forge adapters (github first), the rest walk, excludes,
                     secret redaction
  api/routes.py      thin routes: validate, call the service
  jobs.py            one queue, one worker type, job rows as progress
alembic/             migrations from day one
tests/               42 tests, no network, every model call canned
```

rules the code keeps:

- the brain is pure: every check is unit-testable with canned model outputs
- model_version, score, pitch_view, export are immutable, insert-only
- a draft lens never scores; confirmation includes every inferred weight
- unbound sentences fail the render; export is blocked on honesty failures
- provenance comes from the chunk, never from the model
- the nine w's (thewframework/) are the extraction map: grounding reports
  grounded, partial, or silent per dimension, and silence is surfaced, never
  smoothed over
- secrets are redacted before any content reaches the gateway
- the rest walk reports what it did not read

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

## providers

- `glm`: the real provider. set `BEHOLDER_GLM_API_KEY`, optionally
  `BEHOLDER_GLM_BASE_URL` and `BEHOLDER_GLM_MODEL`
- `demo`: canned responses, no keys
- `mock`: raises unless a responder is injected, for tests

fine-tuned models slot in behind the same task ids later, with no caller
changes: the brain passes task ids, never provider names.
