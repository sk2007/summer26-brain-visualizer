# Brain Viewer Modal Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the BrainViewerModal's left panel with NIfTI file metadata (dimensions, voxel spacing) fetched from a new backend endpoint, and add a "Reload viewer" button that resets the iframe.

**Architecture:** New backend endpoint `GET /api/nifti-info/:id` reads the NIfTI file header from disk (without loading voxel data) using the `nibabel` library already present in the backend requirements, and returns dimensions and voxel spacing. `BrainViewerModal` fetches this on open and renders it below the existing tumor list. A reload button sets a `reloadKey` state integer that forces the iframe to remount.

**Tech Stack:** Python/Flask, nibabel (already in `requirements.txt`), React 19, TypeScript.

## Global Constraints

- The iframe sandbox stays `allow-scripts allow-same-origin allow-forms` — no changes to pycortex internals.
- No new npm dependencies.
- Metadata fetch is best-effort: if the file isn't cached yet (viewer not yet loaded), show a graceful "Not available" state rather than blocking.

---

### Task 1: Backend — NIfTI info endpoint

**Files:**
- Create: `backend/blueprints/nifti_info.py`
- Modify: `backend/app.py`

**Interfaces:**
- Produces: `GET /api/nifti-info/<uuid:nifti_id>` → `{ dims: [number, number, number], voxel_size_mm: [number, number, number] }` or `{ error: string }` with 404

- [ ] **Step 1: Verify nibabel is importable**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && docker-compose exec backend python -c "import nibabel; print(nibabel.__version__)"
```
Expected: prints a version string (e.g. `5.x.x`). If Docker is not running, check `backend/requirements.txt` for `nibabel` and confirm it's present.

- [ ] **Step 2: Create nifti_info.py**

Create `backend/blueprints/nifti_info.py`:

```python
import os
import nibabel as nib
from flask import Blueprint, jsonify, current_app

nifti_info_bp = Blueprint('nifti_info', __name__, url_prefix='/api')


def _find_nifti_path(nifti_id: str, filestore_path: str) -> str | None:
    """Search common subdirectories for a NIfTI file matching the given UUID."""
    for subdir in ('test_db_nifti', 'display_nifti', ''):
        candidate = os.path.join(filestore_path, subdir, f'{nifti_id}.nii.gz')
        if os.path.exists(candidate):
            return candidate
    return None


@nifti_info_bp.route('/nifti-info/<uuid:nifti_id>', methods=['GET'])
def get_nifti_info(nifti_id):
    """Return header metadata for a NIfTI file without loading voxel data."""
    filestore_path = current_app.config['FILESTORE_PATH']
    nifti_path = _find_nifti_path(str(nifti_id), filestore_path)

    if not nifti_path:
        return jsonify({'error': 'NIfTI file not found'}), 404

    try:
        img = nib.load(nifti_path)
        header = img.header
        dims = [int(d) for d in header.get_data_shape()[:3]]
        zooms = [round(float(z), 4) for z in header.get_zooms()[:3]]
        return jsonify({
            'dims': dims,
            'voxel_size_mm': zooms,
        })
    except Exception as e:
        current_app.logger.error(f"Failed to read NIfTI header for {nifti_id}: {e}")
        return jsonify({'error': 'Failed to read NIfTI header'}), 500
```

- [ ] **Step 3: Register the blueprint in app.py**

Open `backend/app.py`. After the last `app.register_blueprint(...)` call, add:

```python
from blueprints.nifti_info import nifti_info_bp
app.register_blueprint(nifti_info_bp)
```

- [ ] **Step 4: Test the endpoint**

With the backend running and at least one NIfTI file accessible:
```bash
# Replace <uuid> with a real NIfTI ID from the database
curl http://localhost:5000/api/nifti-info/<uuid>
```
Expected: `{"dims": [182, 218, 182], "voxel_size_mm": [1.0, 1.0, 1.0]}` (values will vary by file).

For a missing ID:
```bash
curl http://localhost:5000/api/nifti-info/00000000-0000-0000-0000-000000000000
```
Expected: `{"error": "NIfTI file not found"}` with HTTP 404.

- [ ] **Step 5: Commit**

```bash
git add backend/blueprints/nifti_info.py backend/app.py
git commit -m "feat: add GET /api/nifti-info/:id endpoint for NIfTI header metadata"
```

---

### Task 2: Frontend — show metadata and reload button in BrainViewerModal

**Files:**
- Modify: `frontend/src/components/BrainViewerModal.tsx`

**Interfaces:**
- Consumes: `GET /api/nifti-info/:id` → `{ dims: number[], voxel_size_mm: number[] }` from Task 1

- [ ] **Step 1: Add state for metadata and reloadKey**

Inside `BrainViewerModal`, after `const [isFullscreen, setIsFullscreen] = React.useState(false);`, add:

```typescript
const [reloadKey, setReloadKey] = React.useState(0);
const [niftiMeta, setNiftiMeta] = React.useState<{
  dims: number[];
  voxel_size_mm: number[];
} | null>(null);
const [metaError, setMetaError] = React.useState(false);
```

- [ ] **Step 2: Fetch metadata when the modal opens**

Add a `useEffect` (import `useEffect` from React at the top if not already there):

```typescript
React.useEffect(() => {
  if (!isOpen) return;
  setNiftiMeta(null);
  setMetaError(false);
  fetch(`/api/nifti-info/${niftiId}`)
    .then((r) => {
      if (!r.ok) throw new Error('not found');
      return r.json();
    })
    .then((data) => setNiftiMeta(data))
    .catch(() => setMetaError(true));
}, [isOpen, niftiId]);
```

- [ ] **Step 3: Add the RotateCcw icon import for the reload button**

Find the existing import:
```typescript
import { X, Maximize2, Minimize2, Brain } from 'lucide-react';
```
Replace with:
```typescript
import { X, Maximize2, Minimize2, Brain, RotateCcw } from 'lucide-react';
```

- [ ] **Step 4: Add a reload button to the header**

In the header `<div className="flex items-center space-x-2">`, add the reload button before the fullscreen button:

```typescript
<button
  onClick={() => setReloadKey((k) => k + 1)}
  className="p-2 hover:bg-gray-200 rounded-md transition-colors"
  title="Reload viewer"
>
  <RotateCcw className="w-5 h-5" />
</button>
```

- [ ] **Step 5: Apply reloadKey to the iframe**

Find the iframe element:
```typescript
<iframe
  src={viewerUrl}
  className="w-full h-full border-0"
  title={`Brain Viewer - ${title}`}
  sandbox="allow-scripts allow-same-origin allow-forms"
/>
```
Add `key={reloadKey}` so React remounts the iframe when reload is clicked:
```typescript
<iframe
  key={reloadKey}
  src={viewerUrl}
  className="w-full h-full border-0"
  title={`Brain Viewer - ${title}`}
  sandbox="allow-scripts allow-same-origin allow-forms"
/>
```

- [ ] **Step 6: Add metadata display to the left panel**

In the left panel (after the existing tumor summary block), add:

```typescript
{/* NIfTI Metadata */}
<div>
  <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
    File Info
  </p>
  {niftiMeta ? (
    <div className="space-y-1.5 text-xs">
      <div className="flex justify-between">
        <span className="text-gray-400">Dimensions</span>
        <span className="text-white font-mono">{niftiMeta.dims.join(' × ')}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-gray-400">Voxel size</span>
        <span className="text-white font-mono">
          {niftiMeta.voxel_size_mm.map((v) => v.toFixed(2)).join(' × ')} mm
        </span>
      </div>
    </div>
  ) : metaError ? (
    <p className="text-xs text-gray-500">Not available</p>
  ) : (
    <p className="text-xs text-gray-500 animate-pulse">Loading…</p>
  )}
</div>
```

- [ ] **Step 7: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -40
```
Expected: zero errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/BrainViewerModal.tsx
git commit -m "feat: add NIfTI metadata panel and reload button to BrainViewerModal"
```
