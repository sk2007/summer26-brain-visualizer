# Backend Test Suite + CI — Design

**Status:** Approved for planning
**Date:** 2026-07-30
**Branch:** `feature/backend-test-suite`

## Goal

Establish the project's first automated test suite. The backend currently has
zero project tests; the entire recent feature push relied on manual verification
and TypeScript type-checking. This introduces a focused pytest suite covering the
two highest-risk, most-subtle areas of backend logic, plus a CI job that runs it
on every pull request.

## Scope

**In scope:**

- A `backend/tests/` pytest package with fixtures and two test modules.
- Tests for **chart persistence** (`backend/blueprints/chart.py`).
- Tests for **filter / chart-data query logic** (`backend/blueprints/chart_fields.py`).
- A GitHub Actions workflow running the suite against a real Postgres service.
- Minimal dev dependencies (`pytest`, `pytest-cov`).

**Out of scope (explicitly):**

- Tests for the pycortex surface viewer, glass-brain rendering, or NIfTI
  generation (integration-heavy, brittle, low ROI for a first suite).
- Broad coverage of every blueprint route (filters CRUD, patient queries,
  nifti-info, etc.). May follow later.
- **Bug fixes.** This PR is tests-only. Tests assert *current correct* behavior.
  If a test surfaces a genuine bug (e.g. the known `null`-id gap in
  `create_chart`), it is logged as a follow-up — not fixed here — to keep the PR
  focused. Do not write a test that asserts buggy behavior as if it were correct;
  either omit that case or mark it `xfail` with a comment linking the follow-up.
- Any refactor of `app.py` into an application factory.

## Key Constraints (from the codebase)

- **No app factory.** `app.py` constructs the Flask `app` and `db = SQLAlchemy(app)`
  at import time. The test harness must set `DATABASE_URL` to the test database
  **before** importing `app`, so `db` binds to `brain_test`.
- **Lazy imports in blueprints.** `chart.py` and `chart_fields.py` do
  `from app import db, redis_cache` and `from models import ...` *inside* function
  bodies. This means monkeypatching `app.redis_cache` at test time is picked up on
  the next call — no import-time binding to work around.
- **Postgres-specific query constructs.** The query logic uses a `JSON` column
  (`SavedChart.data`) and `db.extract('year', Patients.dob)`. Tests must run
  against real Postgres, not SQLite, or these behaviors diverge silently.
- **Session `user_id`.** `app.before_request` assigns `session['user_id']` (a
  UUID) if absent. Charts and filters are scoped by this value. Tests set it
  explicitly via `client.session_transaction()` to test per-user isolation.

## Architecture

```
backend/
  tests/
    __init__.py
    conftest.py                 # fixtures + seed helpers
    test_chart_persistence.py
    test_filter_queries.py
  pytest.ini                    # test discovery / config
  requirements-dev.txt          # pytest, pytest-cov
```

### Test database strategy — real Postgres

- Target a dedicated **`brain_test`** database (never `brain_dev`), reachable at
  `postgresql://myuser:mypassword@localhost:5432/brain_test` by default,
  overridable via a `TEST_DATABASE_URL` env var.
- A **session-scoped** fixture ensures the `brain_test` database exists: connect
  to the `postgres` maintenance database and `CREATE DATABASE brain_test` if it is
  missing (idempotent). Then bind the app to it and run `db.create_all()`;
  `db.drop_all()` on teardown.
- **Locally:** the existing `docker-compose` Postgres (port 5432) serves this.
- **In CI:** a GitHub Actions `postgres:16` service container serves it.

### Per-test isolation — table truncation

Tables are created once per session (`create_all`). After each test, an
autouse fixture deletes all rows from every table in FK-safe order. This keeps
tests isolated and the suite fast, and is robust against the fact that the app
code itself calls `db.session.commit()` in the persistence paths — which would
fight a SAVEPOINT/nested-transaction rollback scheme. Truncation sidesteps that
entirely and needs no rebinding of `db.session`.

### Redis — in-memory fake via monkeypatch

- A `fake_redis` fixture replaces `app.redis_cache` with a small dict-backed
  object implementing the two methods the code uses: `get_path(key)` and
  `set_path(key, value)`.
- Because blueprints re-import `redis_cache` lazily on each call, the monkeypatch
  is effective without any import-order gymnastics.
- The fake exposes a way to clear its contents so tests can **force a cache miss**
  and exercise the DB-fallback / re-warm path deterministically.

### Fixtures (conftest.py)

| Fixture | Scope | Responsibility |
| --- | --- | --- |
| `app` | session | Set `DATABASE_URL`→test DB before importing `app`; ensure `brain_test` exists; `create_all` / `drop_all`; set `TESTING=True`. |
| `clean_tables` | function (autouse) | Delete all rows from every table after each test, FK-safe order. |
| `client` | function | `app.test_client()`. |
| `fake_redis` | function | Monkeypatch `app.redis_cache` with the dict-backed fake; auto-used by tests that need cache control. |
| seed helpers | n/a | Plain functions that insert `Patients`, `NiftiData`, `TumorMask`, `DoseMask` rows with deterministic values. No `factory_boy`. |

## Test Inventory

### `test_chart_persistence.py` (via the Flask test client)

1. **Defaults on empty state** — `GET /api/charts` with an empty cache and empty
   DB returns the six default charts (`"1"`–`"6"`).
2. **Create persists to DB** — `POST /api/charts` with a user chart: it appears in
   a subsequent `GET`, a matching `SavedChart` row exists in the DB, and no
   default IDs were written to the DB.
3. **Cache miss → DB rehydrate** — after a create, clear the fake redis; `GET`
   returns the user chart (loaded from DB) and re-warms the cache.
4. **Delete is durable** — `DELETE /api/charts/<id>` removes the chart from both
   Redis and DB; after clearing the cache it stays gone (the
   resurrection-prevention guarantee).
5. **Default-ID collision guard** — `POST /api/charts` with `id="1"` returns
   **400** and does not corrupt the cache.
6. **Per-user scoping** — two clients with different `session['user_id']` values
   see independent chart sets; one's created chart is invisible to the other.

### `test_filter_queries.py` (`_get_patient_ids_for_filter` + `/api/chart-data`)

Seed a small deterministic population (a handful of patients with known
ages/sexes/cancers/heights/weights/BP/tumor-counts, plus tumor masks with known
locations/volumes and dose masks with known max doses), then:

1. **No / unknown filter** → returns all patients.
2. **`sex`** categorical filter → only matching patients.
3. **`origin_cancer`** categorical filter → only matching patients.
4. **`age_range` OR union** → two selected age buckets return the union; birth-year
   arithmetic maps ages to the correct patients.
5. **Range fields OR-within / AND-across** — `height_range`, `weight_range`,
   `tumor_count_range`: multiple ranges on one field union; ranges on different
   fields intersect.
6. **Clinical ranges** — `systolic_bp_range`, `diastolic_bp_range`.
7. **Tumor characteristics** — `tumor_location` and `tumor_volume_range` correctly
   join through `NiftiData` → `TumorMask`.
8. **Treatment data** — `dose_range` joins through `NiftiData` → `DoseMask`.
9. **Cross-category AND** — combining, e.g., a `sex` filter with a `dose_range`
   filter returns the intersection.
10. **`/api/chart-data` contract:**
    - same-table x/y (e.g. two patient fields) → aligned `x`/`y` arrays;
    - cross-table pair (patient field vs tumor field) → **400** with the
      explanatory message;
    - unknown field key → **400**;
    - missing `x_field`/`y_field` → **400**;
    - `patient_age` values compute correctly from `dob`.

**Filter seeding:** tests seed stored filters by calling the filters module's
Redis-only `store_filters()` helper (writing to the fake redis) — **not** the
`POST /api/filters` route — so filter creation never triggers on-disk NIfTI
generation. The implementer verifies the exact helper name/signature in
`backend/blueprints/filters.py` during Task setup.

## CI

New workflow: `.github/workflows/backend-tests.yml`.

- **Triggers:** `pull_request` and `push` (so the gate runs on branches and PRs,
  not only on deploy-to-main). The existing `deploy_test.yml` is untouched.
- **Postgres service:** `postgres:16` with `POSTGRES_USER=myuser`,
  `POSTGRES_PASSWORD=mypassword`, `POSTGRES_DB=brain_test`, plus a health check so
  the job waits for readiness.
- **Steps:** checkout → `setup-python@v5` (3.11) → `pip install -r
  backend/requirements.txt -r backend/requirements-dev.txt` → `pytest` from
  `backend/`, with `DATABASE_URL`/`TEST_DATABASE_URL` pointing at the service
  (`localhost:5432`).

## Dependencies

Add `backend/requirements-dev.txt`:

- `pytest`
- `pytest-cov` (coverage reporting; non-blocking threshold to start)

No `factory_boy`, no `fakeredis` — the in-memory Redis fake and seed helpers are
hand-rolled to keep the dependency surface minimal.

## Error Handling & Gotchas (for the implementer)

- **Import order is load-bearing.** `conftest.py` must set the test `DATABASE_URL`
  before the first `import app`. Do it at the top of `conftest.py`, before any
  app/model import.
- **Never point tests at `brain_dev`.** `db.drop_all()` on the dev database would
  wipe local data. The `brain_test` database name is mandatory; fail loudly if the
  resolved URL is not the test DB.
- **`before_request` runs on every test-client request** and assigns a
  `user_id`; to control per-user scoping, set the session explicitly with
  `client.session_transaction()` before issuing requests.
- **App code commits mid-test.** `store_charts` / `delete_chart` call
  `db.session.commit()`. This is why isolation uses table truncation (delete all
  rows after each test) rather than a rollback scheme the app's own commits would
  defeat.

## Success Criteria

- `pytest` passes locally (against the docker-compose Postgres) and in CI.
- The suite covers every case in the Test Inventory.
- CI fails the build when any covered behavior regresses.
- Zero changes to `app.py` or the blueprints — the diff is tests, config, a dev
  requirements file, and one CI workflow.
