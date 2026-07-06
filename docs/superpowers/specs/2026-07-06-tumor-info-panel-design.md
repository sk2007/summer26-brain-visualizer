# Tumor Info Panel in BrainViewerModal

**Date:** 2026-07-06  
**Status:** Approved

## Overview

Add a left-side panel inside `BrainViewerModal` showing the patient's tumor count, each tumor's brain region, and its volume in mm³. Appears in all three viewer types (MRI, Tumor mask, Dose).

## Scope

- Modify `frontend/src/components/BrainViewerModal.tsx` — add panel + new optional props
- Modify `frontend/src/components/PatientSearch.tsx` — pass `tumorList` when opening the modal

No backend changes required.

## Data Flow

`PatientSearch` already fetches `tumorList: TumorItem[]` (with `{ id, location, volume_mm3 }`) when a patient is selected. This data is passed to `BrainViewerModal` as an optional prop. Optional so the modal renders cleanly with a "No tumor data" placeholder if the prop is omitted.

## Interface Changes

```typescript
// Add to BrainViewerModal
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
  tumorList?: TumorItem[];   // new, optional
}
```

## Layout

The modal body becomes a flex row. Left panel is `w-64`, dark-themed, scrollable. Iframe takes `flex-1`.

```
┌─────────────────────────────────────────────────────┐
│  MRI - 3/6/2004          Mri Visualization    [↗][✕] │  header (unchanged)
├──────────────┬──────────────────────────────────────┤
│ TUMOR SUMMARY│                                      │
│              │                                      │
│ 2 detected   │        pycortex brain iframe         │
│              │                                      │
│ ● Frontal    │                                      │
│   42.3 mm³   │                                      │
│              │                                      │
│ ● Occipital  │                                      │
│   18.1 mm³   │                                      │
└──────────────┴──────────────────────────────────────┘
```

## Panel Content

- Section label: "TUMOR SUMMARY" (uppercase, muted)
- Count: "N tumor(s) detected"
- For each tumor: location (brain region) + volume formatted to 1 decimal place in mm³
- Empty/missing state: "No tumor data" placeholder text

## Files Changed

| File | Change |
|---|---|
| `frontend/src/components/BrainViewerModal.tsx` | Add `TumorItem` type, `tumorList?` prop, left panel JSX |
| `frontend/src/components/PatientSearch.tsx` | Pass `tumorList={tumorList}` in all three `setViewerData` calls |
