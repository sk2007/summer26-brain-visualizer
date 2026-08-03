# Scan Info Box Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent fixed overlay on the brain canvas that shows the active cohort context (filter name, patient count, mask type, view type) and, when a patient is selected in PatientSearch, that patient's demographic and scan summary.

**Architecture:** New `ScanInfoBox` component mounted in `viewer/page.tsx`, fed by two existing backend APIs (`/api/filters/stats/{id}` and `/api/patients/{id}/overview`). `selectedPatient` state is lifted from PatientSearch's internal state to `viewer/page.tsx` via an `onPatientSelect` callback prop, so the viewer can pass it to `ScanInfoBox`.

**Tech Stack:** Next.js 15 / React 19 / TypeScript / Tailwind CSS 3 (class-based dark mode). No new dependencies.

## Global Constraints

- Dark mode uses `dark:` Tailwind variants only — no JS theme detection in components.
- UCLA blue (`#2774AE`) is never modified or replaced.
- Box z-index is `z-30` — below side panels (`z-50`) and ThemeToggle (`z-40`).
- Box position: `fixed bottom-4`, left edge = `sidebarWidth + 16px`, with `transition-[left] duration-300 ease-in-out`.
- Box width: `w-72` (~288px).
- Null / missing patient fields are omitted entirely — no "—" or "N/A".
- Both API fetches use `AbortController` for cancellation on prop change / unmount.
- Mask type display map: `tumor` → `Tumor mask`, `mri` → `MRI mask`, `dose` → `Dose mask`.
- View type display map: `surface` → `Surface`, `glass` → `Glass brain`.

---

### Task 1: Lift `selectedPatient` state to viewer/page.tsx

Add an `onPatientSelect` callback to `PatientSearch` and wire it up in `viewer/page.tsx` so the viewer knows which patient is selected.

**Files:**
- Modify: `frontend/src/components/PatientSearch.tsx`
- Modify: `frontend/src/app/viewer/page.tsx`

**Interfaces:**
- Produces for Task 2:
  - `selectedPatient` state in `viewer/page.tsx` with type `{ id: string; name: string } | null`
  - Passed as prop `selectedPatient` to `ScanInfoBox`

- [ ] **Step 1: Add `onPatientSelect` to `PatientSearchProps`**

In `frontend/src/components/PatientSearch.tsx`, the `PatientSearchProps` interface currently ends at line 58. Add the new optional prop:

```ts
interface PatientSearchProps {
  patientSearchShowing: boolean;
  togglePatientSearch: React.Dispatch<React.SetStateAction<boolean>>;
  onWidthChange?: (width: number) => void;
  onFullScreenChange?: (isFullScreen: boolean) => void;
  sidebarWidth?: number;
  onPatientSelect?: (patient: { id: string; name: string } | null) => void;
}
```

- [ ] **Step 2: Call the callback in `handlePatientSelect`**

In PatientSearch, `handlePatientSelect` (line 141) sets local `selectedPatient` state. After the `setSelectedPatient(patient)` call, add:

```ts
props.onPatientSelect?.({ id: patient.id, name: patient.display_name });
```

So the updated function opening looks like:

```ts
const handlePatientSelect = async (patient: PatientSearchResult) => {
  setSelectedPatient(patient);
  props.onPatientSelect?.({ id: patient.id, name: patient.display_name });
  setIsLoadingOverview(true);
  // ... rest unchanged
```

- [ ] **Step 3: Call the callback in `handleBackToSearch`**

In PatientSearch, `handleBackToSearch` (line 196) clears local state. After `setSelectedPatient(null)`, add:

```ts
props.onPatientSelect?.(null);
```

So it becomes:

```ts
const handleBackToSearch = () => {
  setSelectedPatient(null);
  props.onPatientSelect?.(null);
  setPatientOverview(null);
  setMriTimeline([]);
  setTumorList([]);
  setTreatmentList([]);
};
```

- [ ] **Step 4: Add `selectedPatient` state to `viewer/page.tsx`**

In `frontend/src/app/viewer/page.tsx`, add a new state variable after the existing state declarations (around line 35):

```ts
const [selectedPatient, setSelectedPatient] = useState<{ id: string; name: string } | null>(null);
```

- [ ] **Step 5: Pass `onPatientSelect` to `PatientSearch` in `viewer/page.tsx`**

In `viewer/page.tsx`, the `PatientSearch` usage is around line 239–247. Add the `onPatientSelect` prop:

```tsx
{patientSearchShowing && (
  <PatientSearch
    patientSearchShowing={patientSearchShowing}
    togglePatientSearch={setPatientSearchShowing}
    onWidthChange={setPatientSearchWidth}
    onFullScreenChange={setIsPatientSearchFullScreen}
    sidebarWidth={sidebarWidth}
    onPatientSelect={setSelectedPatient}
  />
)}
```

- [ ] **Step 6: Verify TypeScript compilation**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PatientSearch.tsx frontend/src/app/viewer/page.tsx
git commit -m "feat: lift selectedPatient state to viewer/page via onPatientSelect callback"
```

---

### Task 2: Create ScanInfoBox component and mount it

Build the `ScanInfoBox` component — fetching filter stats and patient overview, rendering the fixed overlay — then mount it in `viewer/page.tsx`.

**Files:**
- Create: `frontend/src/components/ScanInfoBox.tsx`
- Modify: `frontend/src/app/viewer/page.tsx`

**Interfaces:**
- Consumes from Task 1:
  - `selectedPatient: { id: string; name: string } | null` from viewer/page.tsx state
  - `activeFilterId: string | null` from viewer/page.tsx state
  - `activeMaskType: string` from viewer/page.tsx state
  - `activeViewType: string` from viewer/page.tsx state
  - `sidebarWidth: number` (80 | 256) from viewer/page.tsx

- [ ] **Step 1: Create `ScanInfoBox.tsx` with the component skeleton**

Create `frontend/src/components/ScanInfoBox.tsx`:

```tsx
'use client';

import React, { useEffect, useState } from 'react';

interface FilterStats {
  filter_name: string;
  total_patients: number;
  current_mask_type: string;
}

interface PatientOverview {
  id: string;
  sex: string;
  height_cm: number;
  weight_kg: number;
  date_of_original_diagnosis: string | null;
  date_of_metastatic_diagnosis: string | null;
  data_summary: {
    tumor_masks: number;
    mri_masks: number;
    dose_masks: number;
  };
}

interface ScanInfoBoxProps {
  activeFilterId: string | null;
  activeMaskType: string;
  activeViewType: string;
  selectedPatient: { id: string; name: string } | null;
  sidebarWidth: number;
}

const MASK_LABELS: Record<string, string> = {
  tumor: 'Tumor mask',
  mri: 'MRI mask',
  dose: 'Dose mask',
};

const VIEW_LABELS: Record<string, string> = {
  surface: 'Surface',
  glass: 'Glass brain',
};

function Skeleton() {
  return (
    <div className="animate-pulse bg-gray-200 dark:bg-gray-600 rounded h-3 w-32" />
  );
}

export default function ScanInfoBox({
  activeFilterId,
  activeMaskType,
  activeViewType,
  selectedPatient,
  sidebarWidth,
}: ScanInfoBoxProps) {
  const [filterStats, setFilterStats] = useState<FilterStats | null>(null);
  const [filterLoading, setFilterLoading] = useState(false);
  const [filterError, setFilterError] = useState(false);

  const [patientOverview, setPatientOverview] = useState<PatientOverview | null>(null);
  const [patientLoading, setPatientLoading] = useState(false);
  const [patientError, setPatientError] = useState(false);

  // Fetch filter stats
  useEffect(() => {
    if (!activeFilterId) {
      setFilterStats(null);
      setFilterError(false);
      return;
    }
    const controller = new AbortController();
    setFilterLoading(true);
    setFilterError(false);
    fetch(`/api/filters/stats/${activeFilterId}?maskType=${activeMaskType}`, {
      signal: controller.signal,
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error('stats fetch failed');
        return r.json();
      })
      .then((data: FilterStats) => {
        setFilterStats(data);
        setFilterLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setFilterError(true);
        setFilterLoading(false);
      });
    return () => controller.abort();
  }, [activeFilterId, activeMaskType]);

  // Fetch patient overview
  useEffect(() => {
    if (!selectedPatient) {
      setPatientOverview(null);
      setPatientError(false);
      return;
    }
    const controller = new AbortController();
    setPatientLoading(true);
    setPatientError(false);
    fetch(`/api/patients/${selectedPatient.id}/overview`, {
      signal: controller.signal,
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error('overview fetch failed');
        return r.json();
      })
      .then((data: PatientOverview) => {
        setPatientOverview(data);
        setPatientLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setPatientError(true);
        setPatientLoading(false);
      });
    return () => controller.abort();
  }, [selectedPatient]);

  const leftOffset = sidebarWidth + 16;

  return (
    <div
      className="fixed bottom-4 z-30 w-72 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm shadow-md rounded-xl p-3 text-sm transition-[left] duration-300 ease-in-out"
      style={{ left: leftOffset }}
    >
      {/* Cohort section */}
      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
        Current View
      </p>
      {!activeFilterId ? (
        <p className="text-gray-400 text-xs">No filter selected</p>
      ) : filterLoading ? (
        <div className="space-y-1.5">
          <Skeleton />
          <Skeleton />
        </div>
      ) : filterError ? (
        <p className="text-gray-400 text-xs">Filter unavailable</p>
      ) : filterStats ? (
        <div className="space-y-0.5">
          <p className="text-gray-700 dark:text-gray-300">
            {filterStats.filter_name} · {filterStats.total_patients} patient{filterStats.total_patients !== 1 ? 's' : ''}
          </p>
          <p className="text-gray-700 dark:text-gray-300">
            {MASK_LABELS[activeMaskType] ?? activeMaskType} · {VIEW_LABELS[activeViewType] ?? activeViewType}
          </p>
        </div>
      ) : null}

      {/* Patient section */}
      {selectedPatient && (
        <div className="border-t border-gray-200 dark:border-gray-700 mt-2 pt-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
            Selected Patient
          </p>
          {patientLoading ? (
            <div className="space-y-1.5">
              <Skeleton />
              <Skeleton />
              <Skeleton />
            </div>
          ) : patientError ? (
            <p className="text-gray-400 text-xs">Patient data unavailable</p>
          ) : patientOverview ? (
            <div className="space-y-0.5">
              <p className="text-gray-700 dark:text-gray-300">{selectedPatient.name}</p>
              {(patientOverview.sex || patientOverview.height_cm || patientOverview.weight_kg) && (
                <p className="text-gray-700 dark:text-gray-300">
                  {[
                    patientOverview.sex,
                    patientOverview.height_cm ? `${patientOverview.height_cm} cm` : null,
                    patientOverview.weight_kg ? `${patientOverview.weight_kg} kg` : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              )}
              {patientOverview.date_of_original_diagnosis && (
                <p className="text-gray-700 dark:text-gray-300">
                  Dx: {patientOverview.date_of_original_diagnosis.slice(0, 10)}
                </p>
              )}
              {patientOverview.date_of_metastatic_diagnosis && (
                <p className="text-gray-700 dark:text-gray-300">
                  Met: {patientOverview.date_of_metastatic_diagnosis.slice(0, 10)}
                </p>
              )}
              <p className="text-gray-700 dark:text-gray-300">
                Tumors {patientOverview.data_summary.tumor_masks} · MRI {patientOverview.data_summary.mri_masks} · Dose {patientOverview.data_summary.dose_masks}
              </p>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Import and mount ScanInfoBox in `viewer/page.tsx`**

Add the import at the top of `viewer/page.tsx` alongside the other component imports:

```ts
import ScanInfoBox from '@/components/ScanInfoBox';
```

Then add the component at the end of the JSX return, just before the closing `</div>` of the root element (after the ThemeToggle block, around line 253):

```tsx
      {/* Scan info box */}
      <ScanInfoBox
        activeFilterId={activeFilterId}
        activeMaskType={activeMaskType}
        activeViewType={activeViewType}
        selectedPatient={selectedPatient}
        sidebarWidth={sidebarWidth}
      />
```

The full updated closing of the return JSX should look like:

```tsx
      {/* Dark mode toggle */}
      <div className="fixed top-4 right-4 z-40">
        <ThemeToggle />
      </div>

      {/* Scan info box */}
      <ScanInfoBox
        activeFilterId={activeFilterId}
        activeMaskType={activeMaskType}
        activeViewType={activeViewType}
        selectedPatient={selectedPatient}
        sidebarWidth={sidebarWidth}
      />
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compilation**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Manual smoke test — cohort section**

Start the dev server (`npm run dev` in `frontend/`) and open the viewer page. Confirm:

1. The info box appears bottom-left, offset from the sidebar.
2. It shows the filter name, patient count, mask type, and view type.
3. Toggling mask type (tumor / MRI / dose) in the sidebar updates the box.
4. Toggling view type (surface / glass brain) updates the box.
5. Collapsing/expanding the sidebar shifts the box left/right smoothly.
6. Dark mode: toggle ThemeToggle — box background, text, and labels switch correctly.

- [ ] **Step 5: Manual smoke test — patient section**

1. Open PatientSearch, search for and click a patient.
2. The patient section appears below the cohort section with a divider.
3. Name, demographics (sex / height / weight — only non-null), diagnosis dates (only if present), and scan counts all display correctly.
4. Click the back arrow in PatientSearch — the patient section disappears.
5. While the patient overview is loading, skeleton pulses appear in the patient section.
6. Dark mode: patient section text and divider switch correctly.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ScanInfoBox.tsx frontend/src/app/viewer/page.tsx
git commit -m "feat: add ScanInfoBox overlay showing cohort and selected patient info"
```
