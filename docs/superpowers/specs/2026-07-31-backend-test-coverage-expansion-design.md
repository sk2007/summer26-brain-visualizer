# Backend Test Coverage Expansion — Design (PROPOSAL)

**Status:** Proposal — plannable (no open decisions).
**Date:** 2026-07-31

## Goal

Extend the backend pytest suite (harness landed 2026-07-30) to cover the two
untested route groups that carry real logic and user data: the **filters CRUD +
current-filter** endpoints and the **patient-query** endpoints. This closes the
largest remaining coverage gaps now that fixtures exist and are cheap to reuse.

## Background / Current State

- The harness (`backend/tests/conftest.py`) provides `client`, `fake_redis`,
  `app`, autouse `clean_tables`, `set_session_user`, and seed helpers
  (`seed_patient`, `seed_tumor`, `seed_dose`) in `backend/tests/seed.py`.
- Covered today: chart persistence, brain-clicks, filter selection logic
  (`_get_patient_ids_for_filter`) and `POST /api/chart-data`.
- **Not covered:** the filters blueprint's own CRUD routes and the patient-query
  routes.

## Scope

**In scope — two new test modules:**

**1. `backend/tests/test_filters_api.py`** — the filters blueprint routes
(`backend/blueprints/filters.py`), which are per-user Redis-scoped like charts:
- `GET /api/filters` — empty state returns the default filter set; after a
  create, includes the new filter.
- `POST /api/filters` — creates a filter; response includes the `nifti_generated`
  flag (added earlier). **Note:** creation calls `generate_display_nifti`; the
  test must avoid real NIfTI generation — verify during planning whether to
  monkeypatch `generate_display_nifti` to a no-op/stub so the test is hermetic
  (recommended) rather than touching the filestore.
- `PUT /api/filters/<id>` — updates name/criteria.
- `DELETE /api/filters/<id>` — removes the filter.
- `GET /api/filters/get_current` and `PUT /api/filters/set_current/<id>` — the
  active-filter round-trip.
- `GET /api/filter-options` — returns the expected category structure
  (patient_demographics / clinical_data / tumor_characteristics / treatment_data)
  against a small seeded population.
- `GET /api/filter-statistics/<id>` — returns total/mask counts consistent with
  seeded data.
- Per-user scoping — two sessions see independent filter sets.

**2. `backend/tests/test_patient_queries.py`** — the patient-query routes
(`backend/blueprints/patient_queries.py`), seeded via the existing helpers:
- `GET /api/patients/search?q=` — partial-match search returns expected patients;
  empty/no-match returns an empty result set.
- `GET /api/patients/<id>/overview` — returns demographics/medical fields for a
  seeded patient; unknown id → appropriate 404/empty.
- `GET /api/patients/count` — matches the seeded patient count.
- `GET /api/patients/<id>/mri-timeline`, `/tumors`, `/treatments` — return the
  seeded masks for that patient (extend seed helpers with an MRI-mask seeder if
  the timeline test needs it — `seed.py` currently seeds tumor and dose masks).

**Out of scope:**
- The viewer/pycortex and glass-brain endpoints (integration-heavy, low ROI —
  same exclusion as the original suite).
- Real NIfTI generation in tests (stub it).
- Frontend tests.

## Design Notes

- Reuse `conftest.py` fixtures and `seed.py` helpers unchanged where possible; add
  a `seed_mri(patient, timepoint)` helper if the MRI-timeline test needs MRI mask
  rows (the `MRIMask` model exists with a `timepoint` column).
- Filters are per-user Redis-scoped: seed/read via the routes with a pinned
  `set_session_user`, or seed Redis directly via the filters module's
  `store_filters` helper (same pattern the chart-data tests use for filters).
- Keep tests hermetic: **no real NIfTI/filestore I/O** — stub
  `generate_display_nifti` for the `POST /api/filters` path.

## Testing

This IS the testing work. Success = the new modules pass and the full suite stays
green (currently 28 tests; this adds roughly 15–20 more). Run from `backend/`
against the `brain_test` Postgres; CI runs them automatically via the existing
`backend-tests.yml` workflow.

## Success Criteria

- Filters CRUD + current-filter + options/statistics routes are covered and pass.
- Patient search/overview/count/timeline/tumors/treatments routes are covered and
  pass.
- No test performs real NIfTI generation or filestore I/O.
- Full suite green locally and in CI.
