# Chart Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users delete individual charts from the Data Visualizations panel by adding a delete button to each chart card.

**Architecture:** `DataView` already holds `activeChartConfigs: Record<string, PlotlyConfig>` keyed by chart ID. Add a `handleDeleteChart(chartId: string)` function that calls `DELETE /api/charts/:id` and removes the entry from local state on success. Wrap each chart `div` in a relative container with an absolute-positioned X button. The backend `DELETE /api/charts/<id>` endpoint already exists in `backend/blueprints/chart.py`.

**Tech Stack:** React 19, TypeScript, lucide-react (already installed — use the `X` icon).

## Global Constraints

- Backend endpoint already exists — no backend changes.
- No new npm dependencies.
- Default charts (IDs "1"–"6") can be deleted just like user-created ones.

---

### Task 1: Add delete functionality to DataView

**Files:**
- Modify: `frontend/src/components/DataView.tsx`

**Interfaces:**
- Consumes: `DELETE /api/charts/:id` → 200 `{ message: string }` or 404 `{ error: string }`

- [ ] **Step 1: Add the X icon import**

In `frontend/src/components/DataView.tsx`, the existing import is:
```typescript
import { LayoutGrid, StretchHorizontal, Maximize2, X } from 'lucide-react'
```
`X` is already imported — no change needed. Confirm by checking the import line.

- [ ] **Step 2: Add the handleDeleteChart function**

Inside the `DataView` component, after the `handleChartCreated` function, add:

```typescript
const handleDeleteChart = async (chartId: string) => {
  try {
    const response = await fetch(`/api/charts/${chartId}`, {
      method: 'DELETE',
      headers: { 'Accept': 'application/json' },
    });
    if (!response.ok) {
      console.error('Failed to delete chart:', chartId);
      return;
    }
    setActiveChartConfigs((prev) => {
      const updated = { ...prev };
      delete updated[chartId];
      return updated;
    });
  } catch (err) {
    console.error('Error deleting chart:', err);
  }
};
```

- [ ] **Step 3: Wrap each chart div in a relative container and add the delete button**

Find the block that renders individual charts (inside the `Object.entries(activeChartConfigs).map(...)` call). Currently each chart is wrapped in:

```typescript
<div
  key={chartId}
  className={`border border-gray-200 rounded-lg overflow-hidden ${...}`}
>
  <Chart plotlyConfig={config} />
</div>
```

Replace with:
```typescript
<div
  key={chartId}
  className={`relative border border-gray-200 rounded-lg overflow-hidden ${
    (isGridLayout && isFullScreen)
      ? 'h-[400px]'
      : isFullScreen
        ? 'h-[500px]'
        : 'h-[300px]'
  }`}
>
  <button
    onClick={() => handleDeleteChart(chartId)}
    className="absolute top-2 right-2 z-10 p-1 bg-white/80 hover:bg-red-100 hover:text-red-600 rounded-md transition-colors shadow-sm"
    title="Delete chart"
  >
    <X className="w-3.5 h-3.5" />
  </button>
  <Chart plotlyConfig={config} />
</div>
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -40
```
Expected: zero errors.

- [ ] **Step 5: Manual test**

Start the dev server (`npm run dev` in `frontend/`) and open the app. Open the Charts panel (sidebar → Charts button). Hover over a chart — verify an X button appears in the top-right corner. Click it and confirm the chart disappears. Reload the page and confirm it is also gone (no longer returned by `GET /api/charts`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/DataView.tsx
git commit -m "feat: add per-chart delete button in DataView"
```
