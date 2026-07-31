# Tech-Debt & Maintenance Cleanup — Design (PROPOSAL)

**Status:** Proposal — plannable (no open decisions). A grab-bag of small,
low-risk items; a plan may split them into a couple of commits.
**Date:** 2026-07-31

## Goal

Clear the accumulated small debt and maintenance items surfaced across the recent
work. Each is individually trivial; grouping them into one spec avoids spawning a
plan per one-liner. None changes user-facing behavior.

## Items

### 1. Extract the shared `TumorItem` interface (frontend)
The `TumorItem` interface (`{ id, location, volume_mm3 }`) is duplicated in
`frontend/src/components/BrainViewerModal.tsx` and
`frontend/src/components/PatientSearch.tsx`. Extract it to a shared types module
(e.g. `frontend/src/types/patient.ts`) and import it in both, so the two can't
drift.

### 2. Hoist default-charts construction to a module constant (backend)
`backend/blueprints/chart.py` `store_charts()` calls `get_default_charts()` on
every invocation just to compute the default-ID set. Compute the default IDs once
at module load — e.g. a module-level `_DEFAULT_CHART_IDS = frozenset(...)` — and
use that in `store_charts`/`create_chart` instead of rebuilding the full dict each
call. Behavior identical; avoids repeated ~3 KB dict construction on every write.

### 3. Rename builtin-shadowing locals (backend)
`create_chart`/`modify_chart` in `chart.py` use `id` and `type` as local variable
names, shadowing Python builtins. Rename to `chart_id` / `chart_type` for
clarity. Pure rename; no behavior change. (Low priority — cosmetic.)

### 4. conftest cleanups (backend tests)
- Remove the unused `import json` at the top of `backend/tests/conftest.py`.
- Add a one-line comment on `FakeRedis.clear()` noting it is a test-only helper
  not present on the real `RedisCache` interface (flagged in review).

### 5. Local `brain_test` CREATEDB convenience (dev ergonomics)
On a fresh local Postgres volume, `myuser` may lack CREATEDB, so the test suite
can't auto-create `brain_test` (it currently requires a one-time manual
`CREATE DATABASE brain_test OWNER myuser;`). Add a convenience so a fresh checkout
"just works" — options (pick during planning):
- a documented one-liner / small `make test-db` target, or
- a docker-compose init script that creates `brain_test` alongside `brain_dev`.
CI is unaffected (its Postgres service pre-creates `brain_test`). Keep this
dev-only; do not change the app's runtime DB config.

### 6. CI action version bumps (maintenance)
GitHub is deprecating the Node 20 runtime; `actions/checkout@v4` and
`actions/setup-python@v5` currently emit a deprecation warning (seen on the
`backend-tests.yml` runs). Bump to the current majors when convenient to clear
the warning. Purely a workflow-file edit; no functional change. Applies to both
`.github/workflows/backend-tests.yml` and `deploy_test.yml`.

## Scope

**In scope:** exactly the six items above.
**Out of scope:** any behavior change, any refactor beyond these named items, the
pre-existing `store_brain_click` in-place dict mutation (harmless; leave unless it
becomes relevant).

## Testing

- Backend items (2, 4): the existing pytest suite must stay green (28 tests) — the
  default-ID constant and conftest edits are covered by existing tests.
- Frontend item (1): `tsc --noEmit` clean.
- CI item (6): YAML validates; the workflow still runs green.
- Item 5 is dev tooling — verify the convenience actually creates `brain_test` on
  a fresh volume.

## Success Criteria

- No duplicated `TumorItem`; both components import the shared type.
- `store_charts` no longer rebuilds the defaults dict per call.
- No builtin shadowing in `create_chart`/`modify_chart` (if item 3 is included).
- conftest has no unused imports; `FakeRedis.clear()` is documented.
- A fresh local checkout can run the suite without manual DB creation.
- CI workflows no longer emit the Node 20 deprecation warning.
- Full backend suite green; `tsc` clean.
