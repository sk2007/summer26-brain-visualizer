# MRI Chronological Playback Mode

**Date:** 2026-07-06  
**Status:** Approved

## Overview

A fullscreen playback mode that lets doctors scrub through a patient's MRI scans in chronological order to observe tumor progression over time. Triggered from the MRI Timeline section of the Patient Stats panel.

## Scope

- New `MRIPlaybackModal` frontend component
- Wire existing Play button stub in `PatientSearch.tsx`
- No backend changes required

## Architecture

### Data flow

`PatientSearch` already fetches `mriTimeline: MRITimelineItem[]` (sorted chronologically) when a patient is selected. On Play click, this array and the patient display name are passed directly to `MRIPlaybackModal` — no additional API calls needed.

Each scan's viewer is served by the existing endpoint:
```
GET /api/viewer/{nifti_id}/test_db_nifti
```
This generates the NIfTI on demand if missing and serves the pycortex WebGL viewer.

### Components

**`MRIPlaybackModal.tsx`** (new)

Props:
```typescript
interface MRIPlaybackModalProps {
  isOpen: boolean;
  onClose: () => void;
  mriScans: MRITimelineItem[];  // already sorted chronologically
  patientName: string;
}
```

State:
- `activeIndex: number` — which scan is currently shown
- `loadedSet: Set<number>` — which iframe indices have fired `onLoad`

**`PatientSearch.tsx`** (modified)

- Add `playbackOpen: boolean` state
- Wire the Play button (line 498) to `setPlaybackOpen(true)`; disable it when `mriTimeline.length === 0`
- Render `<MRIPlaybackModal>` at the bottom of the component

## Layout

```
┌─────────────────────────────────────────────────┐
│ [←] Patient d009db60...    Scan 3 of 8    [✕]  │  top bar
├─────────────────────────────────────────────────┤
│                                                 │
│           pycortex brain viewer                 │  fills remaining height
│         (active iframe, full width)             │
│                                                 │
├─────────────────────────────────────────────────┤
│  3/6/2004 · MRI · Scan 3 of 8                  │  metadata row
│  [◀]  ●──────────○──────────○──────────○  [▶]  │  scrubber
│  1/1/2003    3/6/2004    8/12/2005  ...         │  date labels
└─────────────────────────────────────────────────┘
```

## Iframe Strategy

All N iframes are mounted simultaneously when the modal opens. Hidden iframes use:
```css
opacity: 0; pointer-events: none; position: absolute; inset: 0;
```
The active iframe uses `opacity: 1; position: relative`. This keeps all iframes alive in the DOM so pycortex does not re-initialize when revisiting a scan.

Loading state: while `activeIndex` is not in `loadedSet`, a centered spinner overlay sits on top of the viewer area. The iframe renders underneath; the overlay disappears once `onLoad` fires.

## Scrubber

- `<input type="range" min={0} max={n-1} step={1}>` controls `activeIndex`
- Ticks are evenly spaced (not date-proportional)
- Date labels shown at each tick, formatted as `M/D/YYYY`; truncated to `M/YYYY` when there are more than 6 scans
- Prev/next arrow buttons flank the scrubber; hidden (or disabled) when `n === 1`
- Keyboard left/right arrow keys also step through scans

## Metadata Row

Displayed above the scrubber:
- Scan date (formatted `M/D/YYYY`)
- Data type: always "MRI" in this mode
- Position: "Scan {activeIndex + 1} of {n}"

## Edge Cases

| Scenario | Behavior |
|---|---|
| Single scan | Scrubber and prev/next hidden; fullscreen layout still shown |
| iframe load failure (500/404) | Spinner replaced with "Failed to load scan" error message; other scans still navigable |
| `mriTimeline` empty | Play button disabled; modal never opens |
| Modal closed while loading | Unmounting disposes iframes naturally; no cleanup required |

## Files Changed

| File | Change |
|---|---|
| `frontend/src/components/MRIPlaybackModal.tsx` | New component |
| `frontend/src/components/PatientSearch.tsx` | Wire Play button, render modal |
