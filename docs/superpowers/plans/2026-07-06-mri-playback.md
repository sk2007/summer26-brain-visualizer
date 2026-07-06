# MRI Chronological Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fullscreen MRI playback modal that lets doctors scrub through a patient's MRI scans chronologically to observe tumor progression.

**Architecture:** Two frontend-only changes — a new `MRIPlaybackModal` component that mounts all patient MRI scans as hidden iframes simultaneously (revealing only the active one), and a small wiring change in `PatientSearch` to trigger it. No backend changes required; pycortex renders are served by the existing `/api/viewer/{id}/test_db_nifti` endpoint.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, lucide-react icons.

## Global Constraints

- UCLA blue accent color is `#2774AE` — use for active states, spinner, focused labels
- All new components are `'use client'` (no SSR)
- Tailwind only — no inline style blocks except where dynamic values require it (e.g. `left: ${pct}%`)
- Match existing component patterns: resizable panels use `flex flex-col`, modals use `fixed inset-0 z-[100]`; this modal uses `z-[200]` to sit above `BrainViewerModal`
- No new dependencies — use only packages already in `package.json`

---

### Task 1: Create `MRIPlaybackModal` component

**Files:**
- Create: `frontend/src/components/MRIPlaybackModal.tsx`

**Interfaces:**
- Consumes: nothing from other tasks (self-contained)
- Produces: `export default function MRIPlaybackModal(props: MRIPlaybackModalProps)` — consumed by Task 2

- [ ] **Step 1: Create the file with the full component**

`frontend/src/components/MRIPlaybackModal.tsx`:

```tsx
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { X, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

interface MRITimelineItem {
  id: string;
  date: string;
  timepoint: string;
}

interface MRIPlaybackModalProps {
  isOpen: boolean;
  onClose: () => void;
  mriScans: MRITimelineItem[];
  patientName: string;
}

export default function MRIPlaybackModal({
  isOpen,
  onClose,
  mriScans,
  patientName,
}: MRIPlaybackModalProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [loadedSet, setLoadedSet] = useState<Set<number>>(new Set());

  const n = mriScans.length;

  const goTo = useCallback(
    (index: number) => {
      setActiveIndex(Math.max(0, Math.min(n - 1, index)));
    },
    [n]
  );

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setActiveIndex(0);
      setLoadedSet(new Set());
    }
  }, [isOpen]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') goTo(activeIndex - 1);
      if (e.key === 'ArrowRight') goTo(activeIndex + 1);
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, activeIndex, goTo, onClose]);

  if (!isOpen || n === 0) return null;

  const activeScan = mriScans[activeIndex];
  const isMultiple = n > 1;
  const isActiveLoaded = loadedSet.has(activeIndex);

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString('en-US', {
      month: 'numeric',
      day: 'numeric',
      year: 'numeric',
    });

  const formatTickLabel = (dateString: string) =>
    n > 6
      ? new Date(dateString).toLocaleDateString('en-US', {
          month: 'numeric',
          year: '2-digit',
        })
      : new Date(dateString).toLocaleDateString('en-US', {
          month: 'numeric',
          day: 'numeric',
          year: 'numeric',
        });

  const markLoaded = (index: number) =>
    setLoadedSet((prev) => new Set([...prev, index]));

  return (
    <div className="fixed inset-0 z-[200] bg-black flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-3 bg-gray-900 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center space-x-3 min-w-0">
          <span className="text-white font-semibold text-lg truncate max-w-xs">
            {patientName}
          </span>
          <span className="text-gray-400 text-sm flex-shrink-0">MRI Timeline</span>
        </div>
        <span className="text-gray-300 text-sm font-medium flex-shrink-0">
          Scan {activeIndex + 1} of {n}
        </span>
        <button
          onClick={onClose}
          className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-md transition-colors flex-shrink-0"
          title="Close (Esc)"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Brain viewer area */}
      <div className="flex-1 relative overflow-hidden">
        {/* Loading overlay — sits on top while active iframe hasn't fired onLoad */}
        {!isActiveLoaded && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-black space-y-3">
            <Loader2 className="w-10 h-10 text-[#2774AE] animate-spin" />
            <span className="text-gray-400 text-sm">Loading scan...</span>
          </div>
        )}

        {/* All iframes: active one is on top and visible; others are hidden but stay mounted */}
        {mriScans.map((scan, index) => {
          const isActive = index === activeIndex;
          return (
            <iframe
              key={scan.id}
              src={`/api/viewer/${scan.id}/test_db_nifti`}
              title={`MRI scan ${index + 1} — ${formatDate(scan.date)}`}
              onLoad={() => markLoaded(index)}
              sandbox="allow-scripts allow-same-origin allow-forms"
              style={{
                border: 'none',
                width: '100%',
                height: '100%',
                position: isActive ? 'relative' : 'absolute',
                top: 0,
                left: 0,
                opacity: isActive ? 1 : 0,
                pointerEvents: isActive ? 'auto' : 'none',
                zIndex: isActive ? 1 : 0,
              }}
            />
          );
        })}
      </div>

      {/* Bottom bar */}
      <div className="flex-shrink-0 bg-gray-900 border-t border-gray-700 px-6 py-4 space-y-3">
        {/* Metadata row */}
        <div className="flex items-center space-x-3 text-sm text-gray-300">
          <span className="font-medium text-white">{formatDate(activeScan.date)}</span>
          <span className="text-gray-600">·</span>
          <span>MRI</span>
          <span className="text-gray-600">·</span>
          <span>Scan {activeIndex + 1} of {n}</span>
          {activeScan.timepoint && (
            <>
              <span className="text-gray-600">·</span>
              <span className="text-gray-500">{activeScan.timepoint}</span>
            </>
          )}
        </div>

        {/* Scrubber — hidden when there is only one scan */}
        {isMultiple && (
          <div className="flex items-center space-x-3">
            <button
              onClick={() => goTo(activeIndex - 1)}
              disabled={activeIndex === 0}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0"
              title="Previous scan (←)"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>

            <div className="flex-1 space-y-2">
              <input
                type="range"
                min={0}
                max={n - 1}
                step={1}
                value={activeIndex}
                onChange={(e) => goTo(parseInt(e.target.value, 10))}
                className="w-full h-2 bg-gray-600 rounded-full appearance-none cursor-pointer accent-[#2774AE]"
              />
              {/* Date tick labels — positioned by percentage across the scrubber width */}
              <div className="relative h-4">
                {mriScans.map((scan, index) => (
                  <span
                    key={scan.id}
                    className={`absolute text-xs transform -translate-x-1/2 whitespace-nowrap transition-colors ${
                      index === activeIndex
                        ? 'text-[#2774AE] font-medium'
                        : 'text-gray-500'
                    }`}
                    style={{ left: `${(index / (n - 1)) * 100}%` }}
                  >
                    {formatTickLabel(scan.date)}
                  </span>
                ))}
              </div>
            </div>

            <button
              onClick={() => goTo(activeIndex + 1)}
              disabled={activeIndex === n - 1}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0"
              title="Next scan (→)"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors (or only pre-existing unrelated errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/MRIPlaybackModal.tsx
git commit -m "add MRIPlaybackModal component for chronological MRI playback"
```

---

### Task 2: Wire Play button in `PatientSearch`

**Files:**
- Modify: `frontend/src/components/PatientSearch.tsx`

**Interfaces:**
- Consumes: `MRIPlaybackModal` default export from Task 1
- Produces: nothing (terminal task)

- [ ] **Step 1: Add the import at the top of `PatientSearch.tsx`**

After the existing import on line 4:
```tsx
import BrainViewerModal from './BrainViewerModal';
```

Add:
```tsx
import MRIPlaybackModal from './MRIPlaybackModal';
```

- [ ] **Step 2: Add `playbackOpen` state**

After the existing brain viewer modal state (around line 74–79):
```tsx
// Brain viewer modal state
const [brainViewerOpen, setBrainViewerOpen] = useState(false);
const [viewerData, setViewerData] = useState<{ ... } | null>(null);
```

Add directly below:
```tsx
const [playbackOpen, setPlaybackOpen] = useState(false);
```

- [ ] **Step 3: Replace the Play button stub with a wired version**

Find the existing Play button in the MRI Timeline section (currently has a commented-out onClick):

```tsx
<button
  // onClick={() => handlePlayMRI()} // Add your onClick handler here
  className='p-2 text-[#2774AE] hover:bg-[#2774AE] hover:text-white rounded-md transition-colors'
  title='Play MRI Timeline'
>
  <Play className='w-4 h-4' />
</button>
```

Replace with:

```tsx
<button
  onClick={() => setPlaybackOpen(true)}
  disabled={mriTimeline.length === 0}
  className='p-2 text-[#2774AE] hover:bg-[#2774AE] hover:text-white rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed'
  title={mriTimeline.length === 0 ? 'No MRI scans available' : 'Play MRI Timeline'}
>
  <Play className='w-4 h-4' />
</button>
```

- [ ] **Step 4: Render `MRIPlaybackModal` at the bottom of the component**

Find the closing block near the bottom of `PatientSearch` (the `BrainViewerModal` render):

```tsx
      {/* Brain Viewer Modal */}
      {viewerData && (
        <BrainViewerModal
          isOpen={brainViewerOpen}
          onClose={handleCloseBrainViewer}
          niftiId={viewerData.niftiId}
          title={viewerData.title}
          dataType={viewerData.dataType}
        />
      )}
    </div>
  ) : null;
```

Add the playback modal directly after `BrainViewerModal` and before the closing `</div>`:

```tsx
      {/* MRI Playback Modal */}
      <MRIPlaybackModal
        isOpen={playbackOpen}
        onClose={() => setPlaybackOpen(false)}
        mriScans={mriTimeline}
        patientName={selectedPatient ? selectedPatient.display_name : ''}
      />
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 6: Manual verification in browser**

1. Open http://localhost:3001
2. Click **Patient Stats** in the left sidebar
3. Search for any patient (e.g. type `00`)
4. Click a patient to open their profile
5. Scroll to **MRI Timeline** — confirm the Play button is enabled (blue, not dimmed)
6. Click the Play button — confirm the fullscreen modal opens with a dark background
7. Confirm a loading spinner appears while the first scan loads
8. Once loaded, confirm the brain viewer is visible with the scan date, "Scan 1 of N" in the top bar, and the metadata row below
9. If N > 1: drag the scrubber — confirm the scan number and date in the top bar and metadata row update immediately; confirm the new scan loads (spinner → brain)
10. Click the prev/next arrows — confirm they step through scans and disable at the boundaries
11. Press ← and → keyboard keys — confirm they step through scans
12. Press Escape — confirm the modal closes
13. For a patient with only 1 scan: confirm the scrubber and arrows are not rendered

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PatientSearch.tsx
git commit -m "wire MRI playback modal into patient stats panel"
```
