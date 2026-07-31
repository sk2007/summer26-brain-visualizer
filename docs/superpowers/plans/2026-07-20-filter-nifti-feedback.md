# Filter Creation: NIfTI Generation Failure Feedback

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface a warning in the UI when creating a filter succeeds at the database level but the NIfTI file generation silently fails, so users know the filter exists but won't render on the brain viewer.

**Architecture:** The backend `POST /api/filters` endpoint returns `{'message': 'success: filter added'}` even when NIfTI generation fails (the failure is swallowed in a `try/except`). Change the response to include `nifti_generated: bool`. The frontend `filter.tsx` reads this field and shows an inline warning banner below the newly-created filter row.

**Tech Stack:** Python/Flask, React 19, TypeScript. No new dependencies.

## Global Constraints

- HTTP status code stays 201 — filter creation itself succeeded even if NIfTI failed.
- No change to how the filter ID is managed (the backend stores the client-sent UUID and the frontend keeps using it — this is intentional by design).
- The warning is informational only; the filter row is still added to the list.

---

### Task 1: Include nifti_generated in POST /api/filters response

**Files:**
- Modify: `backend/blueprints/filters.py`

**Interfaces:**
- Produces: `POST /api/filters` → `201 { message: string, nifti_generated: boolean }`

- [ ] **Step 1: Add nifti_generated tracking to create_filter**

Open `backend/blueprints/filters.py`. Find `def create_filter()` (around line 278). The current structure stores the filter and then tries to generate a NIfTI inside a `try/except`. Replace the function body so `nifti_generated` is tracked:

```python
@filters.route('/filters', methods=['POST'])
def create_filter():
    id = request.json.get('id')
    name = request.json.get('name')
    criteria = request.json.get('criteria', {})

    if not id or not name:
        return jsonify({ 'error': 'error: invalid filter' }), 400

    active_filters = get_stored_filters()
    active_filters[id] = { 'name': name, 'criteria': criteria }

    nifti_generated = False
    try:
        mask_type = request.args.get('maskType', 'tumor')
        result_path = generate_display_nifti(id, criteria, mask_type)
        if result_path:
            active_filters[id]['nifti_path'] = result_path
            nifti_generated = True
        else:
            current_app.logger.warning(f"NIfTI generation returned None for filter {id}")
    except Exception as e:
        current_app.logger.error(f"NIfTI generation failed for filter {id}: {e}")

    store_filters(active_filters)

    return jsonify({
        'message': 'success: filter added',
        'nifti_generated': nifti_generated
    }), 201
```

- [ ] **Step 2: Verify the endpoint response shape**

With the backend running:
```bash
curl -X POST http://localhost:5000/api/filters \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<any-valid-session>" \
  -d '{"id": "test-uuid-1234", "name": "Test Filter", "criteria": {}}'
```
Expected: `{"message": "success: filter added", "nifti_generated": true}` (or `false` if NIfTI failed) with HTTP 201.

- [ ] **Step 3: Commit**

```bash
git add backend/blueprints/filters.py
git commit -m "fix: include nifti_generated flag in POST /api/filters response"
```

---

### Task 2: Show a warning banner in filter.tsx when nifti_generated is false

**Files:**
- Modify: `frontend/src/components/filter.tsx`

**Interfaces:**
- Consumes: `POST /api/filters` → `{ message: string, nifti_generated: boolean }` from Task 1

- [ ] **Step 1: Add a niftiWarningFilterId state variable**

Inside the `Filter` component in `frontend/src/components/filter.tsx`, add after the existing modal state declarations:

```typescript
const [niftiWarningFilterId, setNiftiWarningFilterId] = useState<string | null>(null);
```

- [ ] **Step 2: Read nifti_generated from the POST response**

Find the create filter POST `.then(data => { ... })` block (around line 725). Currently:
```typescript
.then(data => {
  setFilters(prev => [...prev, newFilter]);
  setNewFilterName('');
  setNewFilterCriteria({});
  setNewFilterModal(false);
})
```

Replace with:
```typescript
.then(data => {
  setFilters(prev => [...prev, newFilter]);
  setNewFilterName('');
  setNewFilterCriteria({});
  setNewFilterModal(false);
  if (data.nifti_generated === false) {
    setNiftiWarningFilterId(newFilter.id);
  }
})
```

- [ ] **Step 3: Add the warning banner to each filter row**

Inside the filter list map (`filters.map((filter, index) => (...))`) in both the fullscreen and sidepanel layouts, add this warning banner directly after the main row content (before the closing `</div>` of the filter row div):

```typescript
{niftiWarningFilterId === filter.id && (
  <div className="mt-1.5 px-2 py-1.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700 flex items-start gap-1.5">
    <svg className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
      <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
    </svg>
    <span>
      Filter saved, but brain visualization could not be generated. The filter will not render on the viewer.
      <button
        onClick={() => setNiftiWarningFilterId(null)}
        className="ml-1 underline hover:no-underline"
      >
        Dismiss
      </button>
    </span>
  </div>
)}
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -40
```
Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/filter.tsx
git commit -m "feat: show warning banner when filter NIfTI generation fails"
```
