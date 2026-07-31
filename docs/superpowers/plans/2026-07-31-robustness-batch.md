# Robustness Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four low-risk fixes that stop the app failing silently or crashing: a `create_chart` null-id guard, the `/api/brain-clicks` 500 crash, visible frontend error states, and consistent `credentials: 'include'` on chart fetches.

**Architecture:** Two independent tasks — backend (edit `backend/blueprints/chart.py`, add pytest coverage using the existing harness) and frontend (add inline error state to three components and `credentials` to two fetches, verified by `tsc`). No storage redesign, no new dependencies.

**Tech Stack:** Python/Flask, pytest, PostgreSQL, React 19, TypeScript.

## Global Constraints

- Backend changes limited to `backend/blueprints/chart.py` and files under `backend/tests/`.
- Frontend changes limited to `DataView.tsx`, `filter.tsx`, `PatientSearch.tsx`, `NewChartModal.tsx`.
- No changes to `app.py`, other blueprints, models, migrations, or viewer templates.
- No storage redesign; `brain_clicks` stays an in-memory module global (process-local, not durable — accepted for this placeholder).
- No new dependencies (backend or frontend).
- The full backend pytest suite passes; `cd frontend && npx tsc --noEmit` is clean.
- Tests run from `backend/` against the `brain_test` Postgres (running on `localhost:5432`), using the venv at `backend/.venv`.

---

### Task 1: Backend fixes in chart.py (null-id guard + brain-clicks crash)

**Files:**
- Modify: `backend/blueprints/chart.py`
- Modify: `backend/tests/test_chart_persistence.py` (add the null-id test)
- Create: `backend/tests/test_brain_clicks.py`

**Interfaces:**
- Produces: `POST /api/charts` returns 400 when `id` is missing/falsy. `POST /api/brain-clicks` returns 201 (valid) or 400 (missing field); `GET /api/brain-clicks` returns the stored list. A module-level `brain_clicks: list` in `backend/blueprints/chart.py`.

**Context:** `create_chart` currently reads `id = request.json.get('id')` and, after a default-id collision guard, writes `active_charts_copy[id] = {...}` — a falsy id corrupts the Redis cache. Separately, `store_brain_click` and the `get_brain_clicks` route both reference a module global `brain_clicks` that is never defined (NameError → caught → HTTP 500 on every call); the pycortex viewer POSTs to this endpoint on every click. There are also two functions named `get_brain_clicks` — a dead helper returning `[]` (shadowed) and the route handler.

- [ ] **Step 1: Add the null-id test (failing)**

Append to `backend/tests/test_chart_persistence.py`:

```python
def test_create_with_null_id_is_rejected(client, fake_redis):
    resp = client.post("/api/charts", json={
        "id": None,
        "type": "line_chart",
        "title": "x",
        "data": {"xaxis_title": "t", "yaxis_title": "v", "series": []},
    })
    assert resp.status_code == 400
    # Cache not corrupted: defaults still returned.
    get_data = client.get("/api/charts").get_json()
    assert set(get_data.keys()) == {"1", "2", "3", "4", "5", "6"}


def test_create_with_missing_id_is_rejected(client, fake_redis):
    resp = client.post("/api/charts", json={
        "type": "line_chart",
        "title": "x",
        "data": {"xaxis_title": "t", "yaxis_title": "v", "series": []},
    })
    assert resp.status_code == 400
```

- [ ] **Step 2: Create the brain-clicks tests (failing)**

Create `backend/tests/test_brain_clicks.py`:

```python
import pytest


@pytest.fixture(autouse=True)
def reset_brain_clicks():
    """brain_clicks is a module global; reset it around every test."""
    import blueprints.chart as chart_module
    chart_module.brain_clicks.clear()
    yield
    chart_module.brain_clicks.clear()


def test_post_valid_click_returns_201(client):
    resp = client.post("/api/brain-clicks", json={
        "hemi": "left", "vertex": 123, "coords": [1.0, 2.0, 3.0],
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["total_clicks"] == 1


def test_post_missing_field_returns_400(client):
    resp = client.post("/api/brain-clicks", json={"hemi": "left", "vertex": 123})
    assert resp.status_code == 400


def test_get_returns_stored_clicks(client):
    client.post("/api/brain-clicks", json={
        "hemi": "right", "vertex": 9, "coords": [0.0, 0.0, 0.0],
    })
    resp = client.get("/api/brain-clicks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["vertex"] == 9
```

- [ ] **Step 3: Run the new tests to verify they fail**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && \
  source .venv/bin/activate && \
  python -m pytest tests/test_brain_clicks.py \
    tests/test_chart_persistence.py::test_create_with_null_id_is_rejected \
    tests/test_chart_persistence.py::test_create_with_missing_id_is_rejected -v
```

Expected: FAILs — brain-clicks tests fail (currently 500, or `AttributeError` on the missing `brain_clicks` attribute in the reset fixture); null-id tests fail (currently returns 200, not 400).

- [ ] **Step 4: Add the null-id guard to create_chart**

In `backend/blueprints/chart.py`, find the top of `create_chart`:

```python
@chart.route('/charts', methods=['POST'])
def create_chart():
    type = request.json.get('type')
    id = request.json.get('id')
    data = request.json.get('data')
    title = request.json.get('title')

    # Reject IDs that collide with built-in defaults to prevent Redis corruption
    if id in get_default_charts():
        return jsonify({'error': 'chart id conflicts with a default chart'}), 400
```

Insert the null-id guard immediately before the default-id guard:

```python
@chart.route('/charts', methods=['POST'])
def create_chart():
    type = request.json.get('type')
    id = request.json.get('id')
    data = request.json.get('data')
    title = request.json.get('title')

    # Reject a missing/empty id (would write a None key into Redis)
    if not id:
        return jsonify({'error': 'chart id is required'}), 400

    # Reject IDs that collide with built-in defaults to prevent Redis corruption
    if id in get_default_charts():
        return jsonify({'error': 'chart id conflicts with a default chart'}), 400
```

- [ ] **Step 5: Define the brain_clicks global and remove the dead helper**

In `backend/blueprints/chart.py`, find the blueprint definition and the `_user_charts_key` helper near the top:

```python
chart = Blueprint('chart', __name__, url_prefix='/api')

def _user_charts_key():
```

Insert the module global between them:

```python
chart = Blueprint('chart', __name__, url_prefix='/api')

# In-memory store for brain-surface clicks from the pycortex viewer.
# Placeholder: process-local and not durable — per-user/durable storage is
# deferred to the future click→visualization feature.
brain_clicks = []

def _user_charts_key():
```

Then find and DELETE the dead, shadowed helper (it is overridden by the route handler of the same name and returns a throwaway empty list):

```python
def get_brain_clicks():
    """Create a fresh copy of brain clicks for each request."""
    return []

```

Leave the route handler `@chart.route('/brain-clicks', methods=['GET'])` / `def get_brain_clicks(): return jsonify(brain_clicks)` untouched — it now resolves the module global correctly.

- [ ] **Step 6: Run the affected tests and the full suite**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && \
  source .venv/bin/activate && \
  python -m pytest tests/test_brain_clicks.py \
    tests/test_chart_persistence.py -v && \
  python -m pytest -q
```

Expected: the brain-clicks tests pass (3), the chart-persistence tests pass (8 now), and the full suite is green (was 23; now 23 + 2 null-id + 3 brain-clicks = 28 passed).

- [ ] **Step 7: Commit**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && \
git add backend/blueprints/chart.py backend/tests/test_chart_persistence.py backend/tests/test_brain_clicks.py && \
git commit -m "fix: guard null chart id and repair brain-clicks 500 crash

- create_chart rejects a missing/empty id (was corrupting the Redis cache)
- define the missing module-global brain_clicks list; remove the dead
  shadowed get_brain_clicks helper so POST/GET /api/brain-clicks stop 500-ing"
```

---

### Task 2: Frontend error states + credentials consistency

**Files:**
- Modify: `frontend/src/components/DataView.tsx`
- Modify: `frontend/src/components/filter.tsx`
- Modify: `frontend/src/components/PatientSearch.tsx`
- Modify: `frontend/src/components/NewChartModal.tsx`

**Interfaces:**
- Consumes: nothing from Task 1 (independent). Pure frontend.

**Context:** Each component currently only `console.error`s on failure. Add a local `useState<string | null>` error and an inline red message (mirroring the existing `errorMessage` pattern in `NewChartModal.tsx`). Also add `credentials: 'include'` to the chart fetches that omit it.

- [ ] **Step 1: DataView — load error state + credentials**

In `frontend/src/components/DataView.tsx`, add an error state next to the others (after `const [deletingIds, ...]`):

```typescript
  const [loadError, setLoadError] = React.useState<string | null>(null);
```

Replace the `GET /api/charts` effect body:

```typescript
  useEffect(() => {
    fetch('/api/charts', {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      }
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(`HTTP error! status: ${response.status}, message: ${text}`);
            });
        }
        return response.json();
    })
    .then((data: Record<string, PlotlyConfig>) => {
      setActiveChartConfigs(data);
    })
    .catch(err => {
      console.error('Error fetching chart configurations:', err);
      setActiveChartConfigs({});
    });
  }, []);
```

with:

```typescript
  useEffect(() => {
    fetch('/api/charts', {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      },
      credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(`HTTP error! status: ${response.status}, message: ${text}`);
            });
        }
        return response.json();
    })
    .then((data: Record<string, PlotlyConfig>) => {
      setActiveChartConfigs(data);
      setLoadError(null);
    })
    .catch(err => {
      console.error('Error fetching chart configurations:', err);
      setActiveChartConfigs({});
      setLoadError('Failed to load charts. Please try again.');
    });
  }, []);
```

Add `credentials: 'include'` to the DELETE fetch in `handleDeleteChart`:

```typescript
      const response = await fetch(`/api/charts/${chartId}`, {
        method: 'DELETE',
        headers: { 'Accept': 'application/json' },
      });
```

becomes:

```typescript
      const response = await fetch(`/api/charts/${chartId}`, {
        method: 'DELETE',
        headers: { 'Accept': 'application/json' },
        credentials: 'include',
      });
```

Render the error just below the New Chart button. Find:

```tsx
            {/* New Chart Button - matching filter component style */}
            <button
              onClick={() => setNewChartModal(true)}
              className='w-full mb-3 px-3 py-2 bg-[#2774AE] text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors'
            >
              New Chart
            </button>
```

and insert the banner immediately after that `</button>`:

```tsx
            {loadError && (
              <div className='mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded text-sm text-red-700'>
                {loadError}
              </div>
            )}
```

- [ ] **Step 2: filter.tsx — delete error state**

In `frontend/src/components/filter.tsx`, add state after the other modal state (near `const [niftiWarningFilterId, ...]`):

```typescript
  const [deleteError, setDeleteError] = useState<string | null>(null);
```

Replace `handleDelete`:

```typescript
  const handleDelete = async (absoluteIndex: number) => {
    if (filters && filters[absoluteIndex]) {
      const filterToDelete = filters[absoluteIndex];
      
      try {
        const response = await fetch(`/api/filters/${filterToDelete.id}`, {
          method: 'DELETE',
          headers: {
            'Accept': 'application/json'
          },
          credentials: 'include'  // Include session cookies
        });
        
        if (response.ok) {
          setFilters(prev => prev.filter((_, i) => i !== absoluteIndex));
        } else {
          console.error('Failed to delete filter');
        }
      } catch (error) {
        console.error('Error deleting filter:', error);
      }
    }
  };
```

with (clear on success, set on both failure paths):

```typescript
  const handleDelete = async (absoluteIndex: number) => {
    if (filters && filters[absoluteIndex]) {
      const filterToDelete = filters[absoluteIndex];
      
      try {
        const response = await fetch(`/api/filters/${filterToDelete.id}`, {
          method: 'DELETE',
          headers: {
            'Accept': 'application/json'
          },
          credentials: 'include'  // Include session cookies
        });
        
        if (response.ok) {
          setFilters(prev => prev.filter((_, i) => i !== absoluteIndex));
          setDeleteError(null);
        } else {
          console.error('Failed to delete filter');
          setDeleteError('Failed to delete filter. Please try again.');
        }
      } catch (error) {
        console.error('Error deleting filter:', error);
        setDeleteError('Failed to delete filter. Please try again.');
      }
    }
  };
```

Render the banner once, above the filter list. Find the New Filter button block:

```tsx
            {/* New Filter Button */}
            <button
              onClick={() => {
                setNewFilterModal(true);
                setNewFilterCriteria({});
              }}
              className='w-full mb-3 px-3 py-2 bg-[#2774AE] text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors'
            >
              New Filter
            </button>
```

and insert immediately after that `</button>`:

```tsx
            {deleteError && (
              <div className='mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded text-sm text-red-700'>
                {deleteError}
              </div>
            )}
```

- [ ] **Step 3: PatientSearch.tsx — fetch error state**

In `frontend/src/components/PatientSearch.tsx`, add state after `const [isLoadingOverview, ...]`:

```typescript
  const [fetchError, setFetchError] = useState<string | null>(null);
```

In the `searchPatients` function inside the search `useEffect`, set/clear the error. Replace:

```typescript
        const data = await response.json();
        setSearchResults(data.results || []);
      } catch (error) {
        console.error('Error searching patients:', error);
        setSearchResults([]);
      } finally {
```

with:

```typescript
        const data = await response.json();
        setSearchResults(data.results || []);
        setFetchError(null);
      } catch (error) {
        console.error('Error searching patients:', error);
        setSearchResults([]);
        setFetchError('Search failed. Please try again.');
      } finally {
```

In `handlePatientSelect`, replace the `catch` block:

```typescript
    } catch (error) {
      console.error('Error fetching patient data:', error);
      setPatientOverview(null);
      setMriTimeline([]);
      setTumorList([]);
      setTreatmentList([]);
    } finally {
```

with:

```typescript
    } catch (error) {
      console.error('Error fetching patient data:', error);
      setPatientOverview(null);
      setMriTimeline([]);
      setTumorList([]);
      setTreatmentList([]);
      setFetchError('Failed to load patient data. Please try again.');
    } finally {
```

And clear it at the start of a successful select — at the top of `handlePatientSelect`, after `setIsLoadingOverview(true);`, add:

```typescript
    setFetchError(null);
```

Render the banner at the top of the scrollable content area. Find:

```tsx
        {/* Content */}
        <div className='flex-1 overflow-y-auto p-3 max-h-[calc(100vh-3.5rem)]'>
```

and insert immediately after that opening `<div ...>`:

```tsx
          {fetchError && (
            <div className='mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded text-sm text-red-700'>
              {fetchError}
            </div>
          )}
```

- [ ] **Step 4: NewChartModal.tsx — credentials on the chart POST**

In `frontend/src/components/NewChartModal.tsx`, find the `POST /api/charts` call:

```typescript
      const chartRes = await fetch(`${baseURL}/api/charts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(chartData),
      });
```

and add `credentials: 'include'`:

```typescript
      const chartRes = await fetch(`${baseURL}/api/charts`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(chartData),
      });
```

- [ ] **Step 5: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -40
```

Expected: zero errors (no output).

- [ ] **Step 6: Commit**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && \
git add frontend/src/components/DataView.tsx frontend/src/components/filter.tsx \
        frontend/src/components/PatientSearch.tsx frontend/src/components/NewChartModal.tsx && \
git commit -m "feat: show inline errors on chart/filter/patient fetch failures; add credentials to chart fetches"
```

---

## Notes for the executor

- Postgres must be reachable on `localhost:5432` for Task 1 (already running via docker-compose `db`; `brain_test` exists).
- Task 1 and Task 2 are fully independent (backend vs frontend, disjoint files) — either order works, but keep them as separate commits/reviews.
- Do not widen scope: no storage redesign for brain-clicks, no bubble-chart size work, no new test harness for the frontend.
