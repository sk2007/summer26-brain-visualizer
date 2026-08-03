# Dark Mode Design

**Date:** 2026-08-03  
**Status:** Approved

## Overview

Add a dark mode to the Brain Visualizer frontend. The user toggles it via a floating button in the top-right of the main canvas. The preference persists across sessions via `localStorage`. Implementation uses `next-themes` to handle SSR hydration, class toggling, and storage.

---

## Architecture

### Theme mechanism (`next-themes`)

- **`tailwind.config.js`** — add `darkMode: 'class'` so `dark:` utility variants activate when the `dark` class is present on `<html>`.
- **`layout.tsx`** — wrap children in `<ThemeProvider attribute="class" defaultTheme="system" enableSystem>`. Add `suppressHydrationWarning` to `<html>`. The provider handles: toggling `.dark` on `<html>`, reading/writing `localStorage`, respecting OS `prefers-color-scheme` as the initial default, and preventing SSR hydration mismatches.
- **`globals.css`** — no changes. The `.dark {}` CSS variable block is already complete (shadcn/ui scaffold).

### New dependency

```
next-themes  (~3kb, zero transitive deps)
```

---

## Toggle component

**File:** `frontend/src/components/ThemeToggle.tsx` (new)

- Uses `useTheme()` from `next-themes`.
- Renders a `Moon` icon in light mode (click → dark) and a `Sun` icon in dark mode (click → light). Icons sourced from `lucide-react` (already installed).
- Uses a `mounted` guard: renders `null` until after client hydration to prevent icon flash on load.
- Styling: `rounded-full p-2 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm shadow-md text-gray-700 dark:text-gray-200 hover:bg-white dark:hover:bg-gray-700 transition-colors`.

**Placement:** Absolute-positioned `top-4 right-4 z-40` inside the main content area in `viewer/page.tsx`. Anchored to the right viewport edge — does not need to shift when left-side panels open.

---

## Color updates

All components use the same mapping table. `dark:` variants are added alongside existing hardcoded Tailwind classes; no classes are removed.

| Light class | Dark variant added |
|---|---|
| `bg-white` | `dark:bg-gray-900` |
| `bg-gray-50` | `dark:bg-gray-800` |
| `bg-gray-100` | `dark:bg-gray-800` |
| `bg-gray-200` | `dark:bg-gray-700` |
| `text-gray-900` | `dark:text-gray-100` |
| `text-gray-800` | `dark:text-gray-200` |
| `text-gray-700` | `dark:text-gray-300` |
| `text-gray-600` | `dark:text-gray-400` |
| `text-gray-500` | `dark:text-gray-400` |
| `border-gray-300` | `dark:border-gray-600` |
| `border-gray-200` | `dark:border-gray-700` |
| `divide-gray-200` | `dark:divide-gray-700` |
| `hover:bg-gray-50` | `dark:hover:bg-gray-800` |
| `hover:bg-gray-100` | `dark:hover:bg-gray-700` |
| `bg-blue-50` (active filter row) | `dark:bg-blue-900/30` |
| `placeholder-gray-500` | `dark:placeholder-gray-400` |

---

## File change inventory

| File | Change |
|---|---|
| `frontend/tailwind.config.js` | Add `darkMode: 'class'` |
| `frontend/src/app/layout.tsx` | Add `ThemeProvider` wrapper; add `suppressHydrationWarning` to `<html>` |
| `frontend/src/components/ThemeToggle.tsx` | New file — toggle button component |
| `frontend/src/app/viewer/page.tsx` | Mount `ThemeToggle` in top-right of main canvas |
| `frontend/src/components/filter.tsx` | Add `dark:` variants to all hardcoded gray/white classes |
| `frontend/src/components/DataView.tsx` | Add `dark:` variants to hardcoded gray/white classes |
| `frontend/src/components/NewChartModal.tsx` | Add `dark:` variants to modal, form inputs, labels |
| `frontend/src/components/PatientSearch.tsx` | Add `dark:` variants to card backgrounds, inputs, borders |
| `frontend/src/components/BrainViewerModal.tsx` | Add `dark:` variants to modal header and overlay |
| `frontend/src/components/chart.tsx` | Add `dark:` variants to chart container border/background |

## Files explicitly not changed

| File | Reason |
|---|---|
| `frontend/src/components/LeftSidebar.tsx` | UCLA blue (`#2774AE`) is a brand color; stays identical in both modes |
| `frontend/src/components/MRIPlaybackModal.tsx` | Already uses `bg-gray-900` dark styling by design |
| `frontend/src/app/globals.css` | `.dark {}` CSS variable block already complete |
