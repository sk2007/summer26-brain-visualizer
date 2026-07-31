# Brain-Click → Data Visualization — Design (PROPOSAL)

**Status:** Proposal — NOT approved for implementation. Contains open
architectural decisions that require a brainstorm before a plan is written.
**Date:** 2026-07-31

## Goal

Let a user click a location on the rendered brain (surface or glass view) and get
a data visualization scoped to that location — e.g. "how many tumors/patients in
the current cohort involve this region," or a distribution of a metric at that
location. This is the one unchecked item in the README roadmap.

## Current State

- The pycortex viewer template (`frontend/src/app/custom_templates/custom_viewer.html`)
  already captures clicks and POSTs `{hemi, vertex, coords}` to
  `POST /api/brain-clicks`. That endpoint now stores clicks in an in-memory
  module global `brain_clicks` (a placeholder — process-local, not durable, not
  per-user; fixed only to stop the 500 it used to throw). Nothing consumes the
  stored clicks yet.
- Spatial data (tumor/dose masks) currently lives as NIfTI files in the
  filestore plus summary rows in Postgres (`TumorMask`/`DoseMask` with center-of-mass
  and bounding-box columns `x_com…z_max`). There is no fast "which masks contain
  voxel (x,y,z)" query — the voxel data is in files, not the DB.

## Why This Needs Decisions (not yet plannable)

The README TODO already frames the hard part: to answer "what's at this
location" quickly, the app needs spatial data queryable from the database, not
just as files. Options with real tradeoffs:

**A. Bounding-box / center-of-mass approximation (DB-only, no schema change).**
Use the existing `x_min…z_max` / `x_com…z_com` columns to test whether a clicked
voxel falls inside a mask's bounding box (or within a radius of its center).
- Pros: no new storage, no migration, ships fast, uses columns that already exist.
- Cons: approximate — a bounding box overcounts (a click in the box's corner may
  not be inside the actual mask). Good enough for "region-level" answers, not
  voxel-exact.

**B. Region/atlas mapping.** Map the clicked vertex/coords to a named anatomical
region (via an atlas), then query masks/patients by region label (the
`TumorMask.location` column already holds region-like strings).
- Pros: semantically meaningful ("frontal lobe"), aligns with existing
  `tumor_location` data and filters. No per-voxel storage.
- Cons: needs an atlas/vertex→region lookup on the click; resolution limited to
  region granularity.

**C. Voxel data in the database (the README's stated direction).** Store per-mask
voxel occupancy in a queryable form (e.g. run-length or sparse coordinate sets,
or PostGIS/3D-index) so "which masks contain (x,y,z)" is exact and indexed.
- Pros: exact, powerful, enables future spatial features.
- Cons: largest effort — storage-format research, a migration, and rewriting the
  filter-aggregation scripts to populate it. This is a subsystem, not a feature.

**Recommendation:** Ship **B (region mapping)** or **A (bounding-box)** first as a
usable v1 that reuses existing data, and treat **C (voxel-in-DB)** as a separate,
later subsystem if voxel-exact answers are actually needed. Do not build C to
ship the first version of this feature.

## Sketch of a v1 (assuming approach B — region mapping)

1. **Persist clicks per user, durably.** Replace the in-memory `brain_clicks`
   placeholder with per-user Redis (mirroring `stored_charts`/`stored_filters`)
   — or skip persistence entirely if the click is handled synchronously (see
   below). Decision needed.
2. **Resolve click → region.** On click, map `{hemi, vertex, coords}` to a region
   label. Where this mapping lives (frontend viewer JS vs a backend endpoint that
   owns an atlas) is an open decision.
3. **Query endpoint.** `POST /api/location-stats` (name TBD) takes a region (or
   coords) plus the active filter id and returns counts/distributions scoped to
   the current cohort — e.g. tumor count, patient count, mean volume at that
   region.
4. **Display.** Show the result either as a small panel/popover on the viewer or
   as a generated chart in the Charts panel (reuse the existing chart pipeline).
   Decision needed: inline popover vs. push-to-Charts.

## Open Decisions (resolve in a brainstorm before planning)

1. Spatial approach: A (bounding-box), B (region), or C (voxel-in-DB)?
2. Where does vertex/coords → region resolution happen (frontend vs backend atlas)?
3. Result surface: inline popover on the viewer, or a chart pushed to the Charts
   panel?
4. Do clicks need to be stored/durable at all, or is the query synchronous
   (click → immediate stats, nothing persisted)?
5. Does this apply to both the surface and glass views, or surface only to start?

## Out of Scope (for a v1)

- Voxel-exact spatial indexing (approach C) unless explicitly chosen.
- Multi-click / region-comparison workflows.
- Historical click analytics.

## Next Step

This proposal must go through the brainstorming skill to resolve the open
decisions (especially #1) before a `writing-plans` plan is created. It is the
only backlog item that is genuinely architectural; the others are directly
plannable.
