# Brain Modal: Control Hints + Dark Tumor Highlighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent control-hint badge to `BrainViewerModal` and change the per-patient tumor colormap to deep dark red.

**Architecture:** Two independent edits — one React component change and one Python backend change. No new files. No new dependencies.

**Tech Stack:** Next.js / React / Tailwind CSS (frontend), Flask / pycortex / matplotlib (backend)

## Global Constraints

- Do not modify the main filter viewer route (`/api/viewer` with no nifti_id) — only the per-patient route
- Control hint badge must be `pointer-events-none` so it never blocks mouse events to the iframe
- `cmap='Reds'` is a standard matplotlib colormap — no import needed beyond what pycortex already uses

---

### Task 1: Add always-on control hint badge to BrainViewerModal

**Files:**
- Modify: `frontend/src/components/BrainViewerModal.tsx:98-106`

**Interfaces:**
- Produces: A `pointer-events-none` absolute-positioned overlay in the bottom-right of the brain viewer panel

- [ ] **Step 1: Read the current brain viewer panel section**

The iframe is in this block (lines 98–106):
```tsx
{/* Brain viewer iframe */}
<div className="flex-1 bg-gray-100 overflow-hidden">
  <iframe
    src={viewerUrl}
    className="w-full h-full border-0"
    title={`Brain Viewer - ${title}`}
    sandbox="allow-scripts allow-same-origin allow-forms"
  />
</div>
```

- [ ] **Step 2: Replace the brain viewer panel div with one that has `relative` positioning and the hint badge**

Replace that block with:
```tsx
{/* Brain viewer iframe */}
<div className="flex-1 bg-gray-100 overflow-hidden relative">
  <iframe
    src={viewerUrl}
    className="w-full h-full border-0"
    title={`Brain Viewer - ${title}`}
    sandbox="allow-scripts allow-same-origin allow-forms"
  />
  <div className="absolute bottom-3 right-3 pointer-events-none flex gap-3 bg-black/50 text-white text-xs rounded-md px-3 py-1.5 select-none">
    <span>Drag · Rotate</span>
    <span className="text-white/40">|</span>
    <span>Right-drag · Pan</span>
    <span className="text-white/40">|</span>
    <span>Scroll · Zoom</span>
  </div>
</div>
```

- [ ] **Step 3: Visually verify**

Start the dev server (`cd frontend && npm run dev`) and open the brain modal for any patient. Confirm the hint badge appears in the bottom-right corner of the brain panel, does not block mouse interactions with the iframe (drag the brain to test), and is legible against the dark background.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/BrainViewerModal.tsx
git commit -m "feat: add always-on control hint badge to BrainViewerModal"
```

---

### Task 2: Change per-patient tumor colormap to deep dark red

**Files:**
- Modify: `backend/blueprints/viewer.py:122-124`

**Interfaces:**
- Consumes: `current_nii_volume_data` (numpy array, values ≥ 0 for tumor mask)
- Produces: `cortex.Volume` with `vmin=0`, `vmax=data.max()`, `cmap='Reds'`

- [ ] **Step 1: Locate the colormap lines**

In `backend/blueprints/viewer.py`, find this block (around line 122):
```python
# Center colormap at 0 so zero voxels appear neutral (white) and tumor signal appears red
vmax = float(max(abs(current_nii_volume_data.max()), abs(current_nii_volume_data.min()), 1e-6))
current_nii_volume = cortex.Volume(current_nii_volume_data, subject='S1', xfmname='fullhead', vmin=-vmax, vmax=vmax)
```

- [ ] **Step 2: Replace with `vmin=0` and `cmap='Reds'`**

```python
# vmin=0 so background (0) maps to light end; Reds colormap → tumors render as deep dark crimson
vmax = float(max(current_nii_volume_data.max(), 1e-6))
current_nii_volume = cortex.Volume(current_nii_volume_data, subject='S1', xfmname='fullhead', vmin=0, vmax=vmax, cmap='Reds')
```

- [ ] **Step 3: Verify visually**

Open a patient's brain modal. The tumor region that was pale salmon/orange should now be a deep dark red/crimson. Binary masks (0 or 1) will render at the max of `Reds` which is `#67001F` (very dark red). If the backend needs a cache-bust, delete the viewer cache for that patient:
```bash
rm -rf backend/filestore/viewer_cache/<nifti_id>/
```
Then reload the modal.

- [ ] **Step 4: Commit**

```bash
git add backend/blueprints/viewer.py
git commit -m "feat: use Reds colormap with vmin=0 for deep dark tumor highlighting"
```
