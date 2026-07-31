# Bubble-Chart Size Dimension Restoration — Design (PROPOSAL)

**Status:** Proposal — plannable (no open decisions).
**Date:** 2026-07-31

## Goal

Restore the third (bubble size) dimension for bubble charts, which was dropped
when `NewChartModal` was reworked to use DB-backed field pickers. Bubble charts
currently render with uniform-size markers because no `size` array is sent.

## Background / Current State

- The backend chart creator **already supports size**:
  `backend/blueprints/chart_creators/bubble_chart.py` reads `trace_data['size']`,
  sets `marker.size`, `sizemode='area'`, and computes a `sizeref` for
  normalization. No backend chart-creator change is needed.
- The regression is **frontend + data-fetch only**: `NewChartModal.tsx` only
  collects an X field and a Y field and builds `series[0].trace = { x, y }` — it
  never collects or sends a size field. The `POST /api/chart-data` endpoint
  (`backend/blueprints/chart_fields.py`) only returns `{x, y}` for two fields.

## Scope

**In scope:**
- Add an optional **Size field** picker in `NewChartModal`, shown only when the
  selected chart type is `bubble_chart`.
- Extend `POST /api/chart-data` to accept an optional third field and return its
  values, so all three arrays are fetched from the same filtered cohort in one
  aligned request (keeping x/y/size row-aligned).
- Pass the size array through to `series[0].trace.size` when building the bubble
  chart payload.

**Out of scope:**
- Any change to the bubble-chart creator (already supports size).
- Size support for non-bubble chart types.
- A color/4th dimension.

## Design

### Backend — `POST /api/chart-data`
Currently accepts `{filter_id, x_field, y_field}` and returns `{x, y}`. Extend to
accept an optional `size_field`. When present:
- Validate it against `FIELD_REGISTRY` (400 on unknown key), and enforce the same
  **same-table** rule already applied to x/y — the size field must be in the same
  table as x and y (else the arrays misalign). Return the existing 400 with the
  "same category" message if it differs.
- Fetch its values via the existing `_fetch_field_values` and return
  `{x, y, size}`. When `size_field` is absent, behavior is unchanged (`{x, y}`).

### Frontend — `NewChartModal.tsx`
- Add `selectedSizeField` state.
- Render a **Size field** `<select>` (same `fieldDefs` options) only when
  `selectedChartType === 'bubble_chart'`. It is optional.
- In `createChart`, when a size field is selected, include `size_field` in the
  `/api/chart-data` POST body, and put the returned `size` array on
  `series[0].trace.size`.
- The Create button's enable condition stays `chartType && xField && yField`
  (size remains optional — a bubble chart with no size field still works, just
  with uniform markers as today).

## Testing

- **Backend (pytest, harness exists):** extend `test_filter_queries.py` (or a new
  test) — `POST /api/chart-data` with a valid `size_field` returns aligned
  `{x, y, size}` of equal length; a `size_field` from a different table → 400; an
  unknown `size_field` → 400; omitting `size_field` returns `{x, y}` unchanged
  (regression guard).
- **Frontend:** `tsc --noEmit` clean; verify by inspection that the Size picker
  appears only for bubble charts and the size array reaches the payload.

## Success Criteria

- Creating a bubble chart with a Size field renders variably-sized bubbles.
- Non-bubble charts are unaffected; bubble charts without a size field behave as
  they do today.
- `chart-data` stays backward-compatible when `size_field` is omitted.
