# Tumor Info Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dark left-side panel to `BrainViewerModal` that shows the patient's tumor count, brain region, and volume for each tumor.

**Architecture:** Two changes — `BrainViewerModal` gets a new optional `tumorList` prop and its body becomes a flex row (panel + iframe); `PatientSearch` passes its already-fetched `tumorList` state into the modal. No backend changes.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, lucide-react icons.

## Global Constraints

- UCLA blue accent color: `#2774AE` — use for tumor icon tint
- Tailwind only — no inline style blocks
- `tumorList` prop is optional — modal must render correctly with no prop passed
- Panel width: `w-64`, dark background `bg-gray-900`, text `text-white`
- Volume formatted to 1 decimal place with `mm³` suffix
- Section label text: `"TUMOR SUMMARY"` (uppercase, `text-xs font-semibold tracking-widest text-gray-400`)
- Count line: singular `"1 tumor detected"`, plural `"N tumors detected"`, empty: `"No tumor data"`

---

### Task 1: Add tumor panel to `BrainViewerModal`

**Files:**
- Modify: `frontend/src/components/BrainViewerModal.tsx`

**Interfaces:**
- Consumes: nothing from other tasks
- Produces: `BrainViewerModal` accepting `tumorList?: TumorItem[]` — consumed by Task 2

- [ ] **Step 1: Replace the full file contents**

`frontend/src/components/BrainViewerModal.tsx`:

```tsx
import React from 'react';
import { X, Maximize2, Minimize2, Brain } from 'lucide-react';

interface TumorItem {
  id: string;
  location: string;
  volume_mm3: number;
}

interface BrainViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  niftiId: string;
  title: string;
  dataType: 'mri' | 'tumor' | 'dose';
  tumorList?: TumorItem[];
}

export default function BrainViewerModal({
  isOpen,
  onClose,
  niftiId,
  title,
  dataType,
  tumorList = [],
}: BrainViewerModalProps) {
  const [isFullscreen, setIsFullscreen] = React.useState(false);

  if (!isOpen) return null;

  const viewerUrl = `/api/viewer/${niftiId}/test_db_nifti`;

  return (
    <div className="fixed inset-0 z-[100] bg-black bg-opacity-50 flex items-center justify-center p-4">
      <div
        className={`bg-white rounded-lg shadow-xl flex flex-col ${
          isFullscreen ? 'w-full h-full' : 'w-[90vw] h-[80vh] max-w-6xl'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-gray-50 rounded-t-lg">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
            <p className="text-sm text-gray-500 capitalize">{dataType} visualization</p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="p-2 hover:bg-gray-200 rounded-md transition-colors"
              title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
            >
              {isFullscreen ? (
                <Minimize2 className="w-5 h-5" />
              ) : (
                <Maximize2 className="w-5 h-5" />
              )}
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-200 rounded-md transition-colors"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body: tumor panel + brain viewer */}
        <div className="flex flex-1 overflow-hidden rounded-b-lg">
          {/* Tumor info panel */}
          <div className="w-64 flex-shrink-0 bg-gray-900 text-white overflow-y-auto p-4 space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
                Tumor Summary
              </p>
              <p className="text-sm font-medium text-white">
                {tumorList.length === 0
                  ? 'No tumor data'
                  : `${tumorList.length} tumor${tumorList.length !== 1 ? 's' : ''} detected`}
              </p>
            </div>

            {tumorList.length > 0 && (
              <div className="space-y-3">
                {tumorList.map((tumor) => (
                  <div key={tumor.id} className="flex items-start space-x-2">
                    <Brain className="w-4 h-4 text-[#2774AE] mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-white">{tumor.location}</p>
                      <p className="text-xs text-gray-400">{tumor.volume_mm3.toFixed(1)} mm³</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Brain viewer iframe */}
          <div className="flex-1 bg-gray-100 overflow-hidden">
            <iframe
              src={viewerUrl}
              className="w-full h-full border-0"
              title={`Brain Viewer - ${title}`}
              sandbox="allow-scripts allow-same-origin allow-forms"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors (pre-existing errors unrelated to this change are acceptable).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/BrainViewerModal.tsx
git commit -m "add tumor info panel to BrainViewerModal"
```

---

### Task 2: Thread `tumorList` from `PatientSearch` into `BrainViewerModal`

**Files:**
- Modify: `frontend/src/components/PatientSearch.tsx` (line 634)

**Interfaces:**
- Consumes: `tumorList?: TumorItem[]` prop on `BrainViewerModal` from Task 1
- Produces: nothing (terminal task)

- [ ] **Step 1: Add `tumorList` prop to the `BrainViewerModal` render**

Find this block in `frontend/src/components/PatientSearch.tsx` (around line 633):

```tsx
      {viewerData && (
        <BrainViewerModal
          isOpen={brainViewerOpen}
          onClose={handleCloseBrainViewer}
          niftiId={viewerData.niftiId}
          title={viewerData.title}
          dataType={viewerData.dataType}
        />
      )}
```

Replace with:

```tsx
      {viewerData && (
        <BrainViewerModal
          isOpen={brainViewerOpen}
          onClose={handleCloseBrainViewer}
          niftiId={viewerData.niftiId}
          title={viewerData.title}
          dataType={viewerData.dataType}
          tumorList={tumorList}
        />
      )}
```

The `tumorList` state variable is already declared at line 71 of `PatientSearch.tsx` — no import or new state needed.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 3: Manual verification in browser**

1. The dev server should already be running on port 3001 (`PORT=3001 npm run dev` from `frontend/`)
2. Open http://localhost:3001
3. Click **Patient Stats** in the sidebar
4. Search for a patient (e.g. type `00`) and click one
5. Click the eye icon next to any MRI, Tumor, or Dose scan to open `BrainViewerModal`
6. Confirm a dark left panel appears showing "TUMOR SUMMARY", the count line, and a list of tumors with location and volume
7. Confirm the brain viewer iframe takes up the remaining width to the right
8. For a patient with no tumor data (unlikely but possible): confirm "No tumor data" placeholder appears without crashing

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PatientSearch.tsx
git commit -m "pass tumorList into BrainViewerModal"
```
