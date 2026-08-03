# Scan Info Box Design

## Overview

A persistent fixed overlay on the brain canvas that shows users what they are
looking at: the active cohort context and, when a patient is selected, that
patient's demographic and scan summary. It is always visible and never
collapses.

---

## Section 1 — Architecture & Data Flow

### New component

`frontend/src/components/ScanInfoBox.tsx` — a `'use client'` component mounted
directly in `viewer/page.tsx`.

### State lift

`selectedPatient` state is added to `viewer/page.tsx` and passed down as an
`onPatientSelect` callback to `PatientSearch`. PatientSearch calls it whenever
the user clicks a patient row.

### Props

```ts
interface ScanInfoBoxProps {
  activeFilterId: string | null;
  activeMaskType: string;        // 'tumor' | 'mri' | 'dose'
  activeViewType: string;        // 'surface' | 'glass'
  selectedPatient: { id: string; name?: string } | null;
  sidebarWidth: number;          // 80 (collapsed) | 256 (expanded)
}
```

### Data fetching

| Data | Endpoint | When |
|------|----------|------|
| Cohort stats | `GET /api/filters/stats/{activeFilterId}?maskType={activeMaskType}` | On mount and whenever `activeFilterId` or `activeMaskType` changes. Skipped when `activeFilterId` is null. |
| Patient overview | `GET /api/patients/{id}/overview` | Whenever `selectedPatient` changes and is non-null. |

Both fetches are cancelled on unmount / prop change via `AbortController`.

### API response shapes (already implemented in backend)

**Filter stats** — returns: `filter_name`, `total_patients`, `total_tumors`,
`total_mris`, `total_dose_masks`, `current_mask_type`.

**Patient overview** — returns: `id`, `origin_cancer`, `tumor_count`, `sex`,
`height_cm`, `weight_kg`, `systolic_bp`, `diastolic_bp`,
`date_of_original_diagnosis`, `date_of_metastatic_diagnosis`, `data_summary`
(`tumor_masks`, `mri_masks`, `dose_masks`, `total_data_points`).

### PatientSearch change

Add optional prop `onPatientSelect?: (patient: { id: string; name?: string } | null) => void`.
Called with the patient object on selection, `null` on deselect. No other
PatientSearch behaviour changes.

---

## Section 2 — Visual Layout & Placement

### Position

`fixed bottom-4 z-30`, left edge = `sidebarWidth + 16px` (same offset pattern
as side panels). Transitions with `transition-[left] duration-300 ease-in-out`
to follow the sidebar expand/collapse animation.

### Container

```
w-72  bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm
shadow-md rounded-xl p-3 text-sm
```

### Cohort section (always shown)

```
CURRENT VIEW                      ← 10px uppercase tracking-wider text-gray-400
Default · 42 patients             ← filter_name · total_patients
Tumor mask · Surface              ← mask type · view type (capitalized)
```

Labels row: `text-[10px] font-semibold uppercase tracking-wider text-gray-400`

Value rows: `text-gray-700 dark:text-gray-300`

When `activeFilterId` is null: single line `No filter selected` in gray.

### Patient section (shown only when a patient is selected)

Separated from cohort by a `border-t border-gray-200 dark:border-gray-700 mt-2 pt-2`.

```
SELECTED PATIENT                  ← same label style as "CURRENT VIEW"
Patient abc123…                   ← name or id
M · 175 cm · 80 kg               ← sex · height · weight (only present fields)
Dx: 2021-03-15                   ← date_of_original_diagnosis (if present)
Met: 2022-07-01                  ← date_of_metastatic_diagnosis (if present)
Tumors 3 · MRI 2 · Dose 1       ← data_summary counts
```

Null / missing fields are omitted entirely (no "—" or "N/A").

When no patient is selected, the patient section (divider + heading + rows) is
entirely absent.

---

## Section 3 — Dark Mode & Edge Cases

### Dark mode

| Element | Light | Dark |
|---------|-------|------|
| Box background | `bg-white/90` | `dark:bg-gray-800/90` |
| Value text | `text-gray-700` | `dark:text-gray-300` |
| Label text | `text-gray-400` | (same — already muted) |
| Divider | `border-gray-200` | `dark:border-gray-700` |
| Skeleton | `bg-gray-200` | `dark:bg-gray-600` |

### Loading states

Both sections use the same skeleton treatment while their fetch is in-flight:

```html
<div class="animate-pulse bg-gray-200 dark:bg-gray-600 rounded h-3 w-32" />
```

One skeleton line per section replaces all data rows.

### Error states

- Filter fetch error → show `Filter unavailable` in `text-gray-400`. Box stays
  visible.
- Patient fetch error → show `Patient data unavailable` in `text-gray-400`.
  Divider and heading stay; data rows are replaced.

### No active filter

`activeFilterId` is null on initial page load while `GET /api/filters/get_current`
resolves. Cohort section shows `No filter selected`. Fetch is not attempted.

### Z-index

`z-30` — below side panels (`z-50`) and ThemeToggle (`z-40`), above canvas.

### Mask type labels

Map `activeMaskType` values to display strings:

| Value | Display |
|-------|---------|
| `tumor` | `Tumor mask` |
| `mri` | `MRI mask` |
| `dose` | `Dose mask` |

### View type labels

| Value | Display |
|-------|---------|
| `surface` | `Surface` |
| `glass` | `Glass brain` |
