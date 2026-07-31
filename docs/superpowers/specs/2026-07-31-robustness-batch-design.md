# Robustness Batch — Design

**Status:** Approved for planning
**Date:** 2026-07-31
**Branch:** `feature/robustness-batch`

## Goal

A tight batch of four independent, low-risk fixes that stop the app from failing
silently or crashing. No feature work, no storage redesign. Backend fixes are
covered by the pytest suite added in the prior branch; frontend fixes are
verified by inspection and `tsc --noEmit`.

## Scope

**In scope (4 fixes):**

1. `create_chart` null-id guard (backend).
2. `brain-clicks` 500-crash fix (backend).
3. Visible error states in three frontend components.
4. `credentials: 'include'` consistency on chart fetches (frontend).

**Explicitly out of scope:**

- Bubble-chart size-dimension restoration (a feature regression, not robustness —
  belongs with chart work).
- Per-user or durable storage for brain clicks (deferred to the actual
  click→visualization roadmap feature; YAGNI here).
- Any new frontend test harness (none exists; adding one is a separate effort).
- Refactors beyond the named fixes.

## Fix Details

### 1. Backend — `create_chart` null-id guard

**File:** `backend/blueprints/chart.py`, `create_chart()`.

Currently `create_chart` reads `id = request.json.get('id')` and, after the
existing default-id collision guard, writes `active_charts_copy[id] = {...}`. A
missing/`null` id writes a `None` key into Redis (and, on the next store, a `None`
id row is skipped by the default filter but the Redis cache is corrupted for that
user).

**Change:** at the top of `create_chart`, before the default-id guard, reject a
falsy id:

```python
if not id:
    return jsonify({'error': 'chart id is required'}), 400
```

Returns HTTP 400. Order: this guard first, then the existing
`if id in get_default_charts(): return 400` guard.

### 2. Backend — `brain-clicks` 500 crash

**File:** `backend/blueprints/chart.py`.

**Current bug:** `store_brain_click` (POST `/api/brain-clicks`) and the route
`get_brain_clicks` (GET `/api/brain-clicks`) both reference a module global
`brain_clicks` that is never defined → `NameError` → caught by the bare
`except` → HTTP 500 on every call. The pycortex viewer template
(`frontend/src/app/custom_templates/custom_viewer.html`) POSTs `{hemi, vertex,
coords}` to this endpoint on every brain-surface click, so those clicks are
silently 500-ing today. Additionally there are two functions named
`get_brain_clicks`: a helper at line ~197 returning `[]` (dead — shadowed) and
the route handler at line ~362.

**Changes (minimal, no storage redesign):**

- Define a module-level `brain_clicks = []` near the other module-level state
  (e.g. next to the chart helpers). This is an in-memory placeholder matching the
  original intent — not per-user, not durable. That is acceptable for a
  placeholder nothing reads meaningfully yet; durable/per-user storage is part of
  the future click→viz feature.
- Remove the dead, shadowed `get_brain_clicks()` helper (the one returning `[]`)
  so only the route handler named `get_brain_clicks` remains.
- Do not change the endpoints' request/response contracts. The POST already
  validates `hemi`, `vertex`, `coords` (matching the viewer payload) and returns
  201 on success; the GET returns the list.

**Note:** the module-global `brain_clicks` is process-local. Under multiple
gunicorn workers it will not be shared, and it resets on restart. This is an
accepted limitation of the placeholder and is documented here so it is not
mistaken for a bug later.

### 3. Frontend — visible error states

Add local error state + an inline red message (mirroring the existing
`errorMessage` pattern in `NewChartModal.tsx`) on the failure paths that
currently only `console.error`. No new dependencies, no toast system.

- **`frontend/src/components/DataView.tsx`** — the `GET /api/charts` load
  (`.catch`) sets an error message rendered in the panel body instead of silently
  showing "No chart data available".
- **`frontend/src/components/filter.tsx`** — `handleDelete` failure (both the
  non-ok response branch and the `catch`) surfaces an inline message on/near the
  filter list rather than only logging.
- **`frontend/src/components/PatientSearch.tsx`** — the patient search fetch
  and/or the patient-overview fetch failures set a visible message in the results
  area instead of only logging.

Each is a self-contained change: a `useState<string | null>` for the error and a
conditional render. Errors clear on the next successful action (or on retry).

### 4. Frontend — `credentials: 'include'` consistency

Add `credentials: 'include'` to the chart-related fetches that omit it, so they
match the filter/chart-data calls and keep per-user chart scoping correct if the
API ever becomes cross-origin:

- `frontend/src/components/DataView.tsx` — `GET /api/charts` and
  `DELETE /api/charts/<id>`.
- `frontend/src/components/NewChartModal.tsx` — the `POST /api/charts` call
  (the `chart-fields`/`chart-data` calls already include it).

Pure addition; no behavioral change under the current same-origin proxy.

## Testing

**Backend (pytest — harness already exists under `backend/tests/`):**

- `create_chart` null-id → `POST /api/charts` with `{"id": null, ...}` (and with
  `id` omitted) returns 400; the cache is not corrupted (GET still returns the six
  defaults).
- `brain-clicks`:
  - `POST /api/brain-clicks` with a valid `{hemi, vertex, coords}` payload → 201,
    body reports success and a `total_clicks` count.
  - `POST` missing a required field (e.g. no `coords`) → 400.
  - `GET /api/brain-clicks` returns the stored clicks.
- Because `brain_clicks` is a module global, the brain-clicks tests must reset it
  between cases. The test module resets `chart_module.brain_clicks` (e.g. an
  autouse fixture doing `chart_module.brain_clicks.clear()`), so tests are
  order-independent. This reset lives in the brain-clicks test module, not in the
  shared `conftest.py`.

New backend tests go in `backend/tests/` (e.g. extend
`test_chart_persistence.py` for the null-id case and add
`test_brain_clicks.py`). Full suite must stay green.

**Frontend:**

- Verified by `cd frontend && npx tsc --noEmit` (zero errors) and by inspection
  that each error path sets and renders its message. No automated frontend tests
  (no harness).

## Global Constraints

- Backend changes limited to `backend/blueprints/chart.py` and new/edited files
  under `backend/tests/`.
- Frontend changes limited to `DataView.tsx`, `filter.tsx`, `PatientSearch.tsx`,
  and `NewChartModal.tsx`.
- No changes to `app.py`, other blueprints, models, migrations, or the viewer
  templates.
- No storage redesign; no new dependencies (backend or frontend).
- The full backend pytest suite passes; `tsc --noEmit` is clean.

## Success Criteria

- `POST /api/charts` with a null/missing id returns 400; charts still work.
- `POST`/`GET /api/brain-clicks` no longer 500; the viewer's clicks are accepted.
- The three frontend components show a visible message on failure instead of
  failing silently.
- Chart fetches consistently send credentials.
- Backend suite green; `tsc --noEmit` clean.
