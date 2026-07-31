# Default Charts Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the six built-in default charts always visible alongside a user's saved charts (Option 1, decided 2026-07-31), keep them non-deletable/read-only, and never persist them as user rows.

**Architecture:** Refactor `backend/blueprints/chart.py` so the stored set (Redis + DB) holds **only user charts**, and defaults are overlaid at read time (`get_stored_charts = {**defaults, **user_charts}`). Guard `DELETE`/`PUT` against default IDs. Add a small frontend change so DataView doesn't render a delete button on default charts. Backend behavior covered by the existing pytest harness.

**Tech Stack:** Python/Flask, pytest, PostgreSQL, Redis, React 19/TypeScript.

## Global Constraints

- Backend changes limited to `backend/blueprints/chart.py` and `backend/tests/test_chart_persistence.py`.
- Frontend changes limited to `frontend/src/components/DataView.tsx`.
- Default chart IDs are exactly `"1"`–`"6"` (from `get_default_charts()`); they are never written to the DB and cannot be deleted or modified.
- `GET/POST/PUT/DELETE /api/charts` response shapes stay unchanged (defaults are overlaid server-side; no new fields).
- The existing 28-test suite must stay green; new tests are added.
- Tests run from `backend/` against the `brain_test` Postgres (`localhost:5432`), venv at `backend/.venv`.

---

### Task 1: Overlay defaults at read time; guard default IDs (backend)

**Files:**
- Modify: `backend/blueprints/chart.py`
- Modify: `backend/tests/test_chart_persistence.py`

**Interfaces:**
- Produces: `get_user_charts()` → dict of the current user's saved charts only (no defaults). `get_stored_charts()` now returns `{**get_default_charts(), **get_user_charts()}`. `store_charts(charts_dict)` persists only non-default entries. `DELETE`/`PUT` on a default ID return 400.

**Context:** Today `get_stored_charts()` returns the raw stored set (defaults only on cold start; the user's set once they've saved anything — so defaults vanish after the first save). We invert this: store user charts only, always overlay defaults on read.

- [ ] **Step 1: Add the new-behavior tests (failing)**

Append to `backend/tests/test_chart_persistence.py` (reuses the existing `_line_chart_payload` helper and fixtures already in that file):

```python
def test_defaults_present_alongside_saved_chart(client, fake_redis):
    import uuid
    chart_id = str(uuid.uuid4())
    client.post("/api/charts", json=_line_chart_payload(chart_id))

    data = client.get("/api/charts").get_json()
    # Defaults AND the user chart are both present.
    assert set(data.keys()) == {"1", "2", "3", "4", "5", "6", chart_id}


def test_delete_default_chart_is_rejected(client, fake_redis):
    resp = client.delete("/api/charts/1")
    assert resp.status_code == 400
    data = client.get("/api/charts").get_json()
    assert set(data.keys()) == {"1", "2", "3", "4", "5", "6"}


def test_modify_default_chart_is_rejected(client, fake_redis):
    resp = client.put("/api/charts/1", json={
        "type": "line_chart",
        "title": "hacked",
        "data": {"xaxis_title": "t", "yaxis_title": "v", "series": []},
    })
    assert resp.status_code == 400


def test_defaults_never_written_to_db_after_save(client, fake_redis):
    import uuid
    from models import SavedChart
    chart_id = str(uuid.uuid4())
    client.post("/api/charts", json=_line_chart_payload(chart_id))
    # Only the user chart is persisted; no default IDs in the DB.
    ids = {c.id for c in SavedChart.query.all()}
    assert ids == {chart_id}
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && source .venv/bin/activate && \
  python -m pytest tests/test_chart_persistence.py -k \
  "defaults_present_alongside or delete_default or modify_default or defaults_never_written" -v
```

Expected: FAILs — `test_defaults_present_alongside_saved_chart` currently returns only `{chart_id}` (defaults vanish after save); `test_delete_default_chart_is_rejected` and `test_modify_default_chart_is_rejected` currently return 200, not 400.

- [ ] **Step 3: Add `get_user_charts()` and rewrite `get_stored_charts()`**

In `backend/blueprints/chart.py`, replace the whole `get_stored_charts()` function (currently lines ~16–45):

```python
def get_stored_charts():
    """Load charts for the current user: Redis first, then DB, then defaults."""
    from app import redis_cache
    from models import SavedChart
    import json

    charts_key = _user_charts_key()
    user_id = session.get('user_id', 'anonymous')

    # 1. Try Redis
    raw = redis_cache.get_path(charts_key)
    if raw:
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        return json.loads(raw)

    # 2. Redis miss: load from DB
    db_charts = SavedChart.query.filter_by(user_id=user_id).all()
    if db_charts:
        charts_dict = {
            c.id: {'type': c.chart_type, 'title': c.title, 'data': c.data}
            for c in db_charts
        }
        store_charts(charts_dict)          # warm the cache
        return charts_dict

    # 3. No saved charts: return defaults (do NOT persist defaults to DB)
    defaults = get_default_charts()
    store_charts(defaults)
    return defaults
```

with:

```python
def get_user_charts():
    """The current user's SAVED charts only (no defaults): Redis, then DB, then {}."""
    from app import redis_cache
    from models import SavedChart
    import json

    charts_key = _user_charts_key()
    user_id = session.get('user_id', 'anonymous')

    # 1. Try Redis (holds user charts only)
    raw = redis_cache.get_path(charts_key)
    if raw:
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        return json.loads(raw)

    # 2. Redis miss: load user charts from DB and warm the cache
    db_charts = SavedChart.query.filter_by(user_id=user_id).all()
    charts_dict = {
        c.id: {'type': c.chart_type, 'title': c.title, 'data': c.data}
        for c in db_charts
    }
    store_charts(charts_dict)              # warm cache (user-only; may be {})
    return charts_dict


def get_stored_charts():
    """Built-in defaults are always overlaid with the user's saved charts."""
    return {**get_default_charts(), **get_user_charts()}
```

- [ ] **Step 4: Make `store_charts` persist user charts only**

Replace the Redis-write portion of `store_charts()`. Currently it writes the whole dict to Redis, then computes `user_chart_ids`:

```python
    # Always update Redis
    redis_cache.set_path(charts_key, json.dumps(charts_dict))

    # Skip DB writes for the built-in default IDs ("1"–"6")
    default_ids = set(get_default_charts().keys())
    user_chart_ids = set(charts_dict.keys()) - default_ids
    if not user_chart_ids:
        return
```

with (strip defaults before writing Redis so the cache holds user charts only):

```python
    # Persist user charts only; defaults are overlaid at read time and never stored.
    default_ids = set(get_default_charts().keys())
    user_charts = {k: v for k, v in charts_dict.items() if k not in default_ids}

    # Always update Redis (user-only view)
    redis_cache.set_path(charts_key, json.dumps(user_charts))

    user_chart_ids = set(user_charts.keys())
    if not user_chart_ids:
        return
```

The DB upsert loop below is unchanged, but change its body to read from `user_charts` instead of `charts_dict`:

```python
        for chart_id in user_chart_ids:
            info = charts_dict[chart_id]
```

becomes:

```python
        for chart_id in user_chart_ids:
            info = user_charts[chart_id]
```

- [ ] **Step 5: Point create/modify/delete at the user set and guard defaults**

In `create_chart` (`chart.py` ~line 249), change the read to the user set (the new chart is a user chart; defaults are overlaid on read):

```python
    # Store the chart definition
    active_charts_copy = get_stored_charts() # Get charts from Redis
```

becomes:

```python
    # Store the chart definition (operate on the user's own charts)
    active_charts_copy = get_user_charts()
```

In `modify_chart` (~line 266), add a default-ID guard at the top of the body and switch to the user set:

```python
def modify_chart(id):
    type = request.json.get('type')
    data = request.json.get('data')
    title = request.json.get('title') # Also get title for modification

    active_charts_copy = get_stored_charts() # Get charts from Redis
    if id not in active_charts_copy:
        return jsonify({ 'error': 'invalid chart id' }), 404 # Use 404 for not found
```

becomes:

```python
def modify_chart(id):
    type = request.json.get('type')
    data = request.json.get('data')
    title = request.json.get('title') # Also get title for modification

    # Default charts are read-only baseline examples.
    if id in get_default_charts():
        return jsonify({ 'error': 'cannot modify a default chart' }), 400

    active_charts_copy = get_user_charts()
    if id not in active_charts_copy:
        return jsonify({ 'error': 'invalid chart id' }), 404 # Use 404 for not found
```

In `delete_chart` (~line 303), add a default-ID guard and switch to the user set:

```python
def delete_chart(id):
    active_charts_copy = get_stored_charts()
    if id not in active_charts_copy:
        return jsonify({ 'error': 'no such chart exists' }), 404
```

becomes:

```python
def delete_chart(id):
    # Default charts cannot be deleted.
    if id in get_default_charts():
        return jsonify({ 'error': 'cannot delete a default chart' }), 400

    active_charts_copy = get_user_charts()
    if id not in active_charts_copy:
        return jsonify({ 'error': 'no such chart exists' }), 404
```

The rest of `delete_chart` (DB delete first, then `del active_charts_copy[id]`, `store_charts(active_charts_copy)`) is unchanged.

- [ ] **Step 6: Run the full suite**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && source .venv/bin/activate && \
  python -m pytest -q
```

Expected: all green — the 4 new tests pass and the existing 28 still pass (was 28; now 32 passed). If any pre-existing test fails, STOP and re-check the refactor (existing tests were written to the old contract but should hold: empty state → 6 defaults; create → chart appears; delete/cache-miss → back to 6 defaults; per-user isolation unchanged).

- [ ] **Step 7: Commit**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && \
git add backend/blueprints/chart.py backend/tests/test_chart_persistence.py && \
git commit -m "feat: always show default charts alongside saved charts (read-only defaults)

Store user charts only; overlay the six defaults at read time. Reject
DELETE/PUT on default IDs. Defaults are never persisted as user rows."
```

---

### Task 2: Hide the delete button on default charts (frontend)

**Files:**
- Modify: `frontend/src/components/DataView.tsx`

**Interfaces:**
- Consumes: `GET /api/charts` returns defaults (keys `"1"`–`"6"`) merged with the user's charts (UUID keys).

**Context:** Every chart card renders a hover delete (✕) button. Default charts are now non-deletable server-side (400), so the button should not appear on them — otherwise clicking it just surfaces the "Failed to delete chart" error we added.

- [ ] **Step 1: Add a default-ID set and gate the delete button**

In `frontend/src/components/DataView.tsx`, add a module-level constant near the top (after the imports, before the component):

```typescript
const DEFAULT_CHART_IDS = new Set(['1', '2', '3', '4', '5', '6']);
```

Find the delete button inside the chart map:

```tsx
                        <button
                          type="button"
                          onClick={() => handleDeleteChart(chartId)}
                          disabled={deletingIds.has(chartId)}
                          className="absolute top-2 right-2 z-10 p-1 opacity-0 group-hover:opacity-100 bg-white/80 hover:bg-red-100 hover:text-red-600 rounded-md transition-[opacity,colors] shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                          title="Delete chart"
                          aria-label="Delete chart"
                        >
                          <X className="w-3.5 h-3.5" aria-hidden="true" />
                        </button>
```

and wrap it so it only renders for non-default charts:

```tsx
                        {!DEFAULT_CHART_IDS.has(chartId) && (
                          <button
                            type="button"
                            onClick={() => handleDeleteChart(chartId)}
                            disabled={deletingIds.has(chartId)}
                            className="absolute top-2 right-2 z-10 p-1 opacity-0 group-hover:opacity-100 bg-white/80 hover:bg-red-100 hover:text-red-600 rounded-md transition-[opacity,colors] shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Delete chart"
                            aria-label="Delete chart"
                          >
                            <X className="w-3.5 h-3.5" aria-hidden="true" />
                          </button>
                        )}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit
```

Expected: exit 0, no output.

- [ ] **Step 3: Commit**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && \
git add frontend/src/components/DataView.tsx && \
git commit -m "feat: hide delete button on default charts in DataView"
```

---

## Notes for the executor

- Postgres must be reachable on `localhost:5432` (docker-compose `db`; `brain_test` exists).
- Do not change the `GET /api/charts` response shape — defaults are overlaid server-side, keyed `"1"`–`"6"`, and render before user charts (Python dict merge preserves that order).
- Keep scope to Option 1: no per-user "hide defaults" toggle, no response-shape changes.
