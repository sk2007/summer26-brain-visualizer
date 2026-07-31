# Default Charts + Saved Charts Merge — Design (PROPOSAL)

**Status:** DECIDED (Option 1 — always-present defaults) — plannable.
**Date:** 2026-07-31
**Decision (2026-07-31):** Option 1 chosen — the six defaults are always visible
alongside a user's saved charts and are not deletable.

## Goal

Decide and implement consistent behavior for how the six built-in default charts
coexist with a user's saved charts. Today there is an asymmetry: a user with zero
saved charts sees the six defaults, but as soon as they save one custom chart they
see **only** their charts and the defaults disappear.

## Background / Current State

`backend/blueprints/chart.py` `get_stored_charts()`:
- **Redis hit** → returns whatever is cached (defaults or the user's set).
- **Redis miss, DB has rows** → returns only the user's DB charts (defaults not
  included).
- **Redis miss, DB empty** → returns the six defaults (and caches them).

So the defaults are a "cold start" fallback, not a persistent baseline. The moment
a user creates a chart, `store_charts` writes their set (user chart only) and the
defaults are gone from their view. This surprised the reviewer during the
persistence work and is a genuine UX asymmetry.

## The Product Decision

Two coherent behaviors; pick one:

**Option 1 — Defaults are always present (merge).** Every user always sees the six
defaults plus any charts they've saved. Defaults are read-only baseline examples.
- Pros: consistent, never "loses" the examples, predictable.
- Cons: users can't remove the defaults from their view; the panel always has six
  demo charts even for power users who want a clean slate.

**Option 2 — Defaults are a starter set the user owns (current-ish, made
consistent).** Defaults seed a brand-new user once; after that the user's set is
authoritative and defaults only reappear if the user has nothing.
- Pros: users can curate/clear their panel; matches "your charts are yours."
- Cons: keeps the current behavior where creating one chart hides the defaults —
  the very asymmetry that prompted this.

**Recommendation: Option 1 (always-present defaults), with the defaults clearly
non-deletable.** It removes the surprise and keeps the panel useful as a
reference, and it matches how the default IDs ("1"–"6") are already treated as
special (never written to the DB, rejected on create-collision).

## Design (assuming Option 1)

`get_stored_charts()` returns, for every path, **the six defaults merged with the
user's saved charts** (user charts keyed by their UUIDs; defaults keyed "1"–"6").
- **Redis hit** → merge defaults into the cached user set before returning (or
  cache only user charts and always overlay defaults at read time).
- **Redis miss, DB has rows** → `{**get_default_charts(), **user_db_charts}`.
- **Redis miss, DB empty** → the six defaults (unchanged).
- `store_charts` continues to skip default IDs for both Redis-diff and DB (already
  does for DB); ensure defaults are not persisted as user rows.
- **Deletion:** `DELETE /api/charts/<id>` for a default ID ("1"–"6") should be
  rejected (400 or a no-op with a clear response) since defaults are baseline —
  confirm this in the plan. Deleting a user chart behaves as today.

Overlaying defaults at read time (rather than baking them into the stored set)
keeps the stored data clean (user charts only) and makes the defaults trivially
updatable.

## Decision (resolved)

**Option 1 (always-present defaults) was chosen** on 2026-07-31. The six defaults
are always visible alongside a user's saved charts and are read-only /
non-deletable. Option 2 is not being pursued. The design below is final.

## Testing

- **Backend (pytest, harness exists):** with Option 1 — a user who has saved one
  chart sees defaults + their chart (both Redis-hit and Redis-miss paths); default
  IDs are never written to the DB; deleting a default ID is rejected; deleting a
  user chart leaves the defaults intact. Extend `test_chart_persistence.py`.

## Success Criteria (Option 1)

- The six defaults are always visible alongside a user's saved charts.
- Defaults are never persisted as user DB rows and cannot be deleted.
- Saving or deleting a user chart never removes the defaults from view.
