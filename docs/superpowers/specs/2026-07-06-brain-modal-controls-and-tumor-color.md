# Brain Modal: Control Hints + Dark Tumor Highlighting

**Date:** 2026-07-06

## Summary

Two targeted improvements to `BrainViewerModal`:
1. Surface a persistent control-hint badge so users know how to pan, rotate, and zoom the 3D brain.
2. Make tumor regions appear in a very dark red/crimson color instead of the current pale salmon.

---

## 1. Control Hints Overlay

### Context
The pycortex WebGL viewer (`movement.js`) already supports full 3D mouse interaction:
- **Left-drag** — rotate
- **Right-drag** — pan
- **Scroll** — zoom

These controls work through the iframe as-is. The only gap is discoverability.

### Change
Add a persistent, always-visible control-hint badge in the bottom-right corner of the brain viewer panel inside `BrainViewerModal`. The badge sits as a React overlay on top of the iframe container (not inside the iframe), using absolute positioning.

**Content:** `Drag · Rotate   Right-drag · Pan   Scroll · Zoom`

**Visual:** Small pill badge, dark semi-transparent background (`bg-black/50`), white text, `text-xs`, pointer-events-none so it never blocks mouse events from reaching the iframe.

**File:** `frontend/src/components/BrainViewerModal.tsx`

---

## 2. Dark Tumor Highlighting

### Context
In `backend/blueprints/viewer.py`, the colormap is currently:
```python
vmax = float(max(abs(data.max()), abs(data.min()), 1e-6))
cortex.Volume(..., vmin=-vmax, vmax=vmax)
```
Centering at 0 spreads the colormap across both sides, leaving tumor voxels (positive values) mapping to pale warm colors in the middle of pycortex's default diverging palette.

### Change
For the per-patient nifti viewer route (`/api/viewer/<nifti_id>/<nifti_dir>`), change to:
- `vmin=0` — background (zero) maps to the neutral/light end
- `vmax=data.max()` (floored at `1e-6`) — tumor values fill the full range
- `cmap='Reds'` — matplotlib colormap that runs white (0) → dark crimson `#67001F` (1.0)

Binary tumor masks (values 0 or 1) will hit the max and render as deep dark red. Probability/density maps will grade from light pink to dark crimson.

The main filter viewer route (no nifti_id) already has its own colormap logic and is left unchanged.

**File:** `backend/blueprints/viewer.py`

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/BrainViewerModal.tsx` | Add always-on control-hint badge overlay |
| `backend/blueprints/viewer.py` | Change colormap: `vmin=0`, `cmap='Reds'` for per-patient viewer |

---

## Out of Scope
- No changes to main viewer page (`/api/viewer` filter route)
- No changes to GlassBrainViewer
- No new mouse handling or iframe JS injection
