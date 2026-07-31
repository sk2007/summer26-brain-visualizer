# Chart Field Selection (Database-Driven) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual comma-separated X/Y value inputs in the New Chart modal with dropdowns that let users pick real patient data columns; the backend fetches and returns the actual values for the active filter.

**Architecture:** Two new backend endpoints. `GET /api/chart-fields` returns a static registry of available fields (name, label, type). `POST /api/chart-data` accepts a filter ID and two field names and returns computed `{ x: any[], y: any[] }` arrays by querying the PostgreSQL database. The `NewChartModal` frontend replaces text inputs with field-picker dropdowns; on submit it calls `/api/chart-data` to fetch values before calling `POST /api/charts` with the resolved data. The existing `POST /api/charts` format is unchanged — only the frontend changes how it populates the series.

**Tech Stack:** Python/Flask, SQLAlchemy, PostgreSQL, React 19, TypeScript.

## Global Constraints

- Do not change `POST /api/charts` request/response shape — `DataView` and `Chart` components depend on it.
- Field queries must respect the active filter (patient sub-set) — they must not return data for the entire database when a filter is active.
- No new npm dependencies.

---

### Task 1: Backend — chart fields registry endpoint

**Files:**
- Create: `backend/blueprints/chart_fields.py`
- Modify: `backend/app.py`

**Interfaces:**
- Produces: `GET /api/chart-fields` → `{ fields: FieldDef[] }` where `FieldDef = { key: string; label: string; type: "numeric" | "categorical" }`

- [ ] **Step 1: Create chart_fields.py with the field registry and endpoint**

Create `backend/blueprints/chart_fields.py`:

```python
from flask import Blueprint, jsonify
from models import Patients, TumorMask, DoseMask, MRIMask, NiftiData
from app import db
from sqlalchemy import func, extract
import datetime

chart_fields_bp = Blueprint('chart_fields', __name__, url_prefix='/api')

# Registry of queryable fields. key = the string the frontend sends back.
FIELD_REGISTRY = {
    # ── Patient demographics ───────────────────────────────────────────────
    'patient_age': {
        'label': 'Patient Age (years)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_height_cm': {
        'label': 'Height (cm)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_weight_kg': {
        'label': 'Weight (kg)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_systolic_bp': {
        'label': 'Systolic BP (mmHg)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_diastolic_bp': {
        'label': 'Diastolic BP (mmHg)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_tumor_count': {
        'label': 'Tumor Count',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_sex': {
        'label': 'Sex',
        'type': 'categorical',
        'table': 'patient',
    },
    'patient_origin_cancer': {
        'label': 'Cancer Type',
        'type': 'categorical',
        'table': 'patient',
    },
    # ── Tumor mask stats ──────────────────────────────────────────────────
    'tumor_volume_mm3': {
        'label': 'Tumor Volume (mm³)',
        'type': 'numeric',
        'table': 'tumor',
    },
    'tumor_location': {
        'label': 'Tumor Location',
        'type': 'categorical',
        'table': 'tumor',
    },
    # ── Dose mask stats ────────────────────────────────────────────────────
    'dose_max_dose': {
        'label': 'Max Dose (Gy)',
        'type': 'numeric',
        'table': 'dose',
    },
    'dose_volume_mm3': {
        'label': 'Dose Volume (mm³)',
        'type': 'numeric',
        'table': 'dose',
    },
}


@chart_fields_bp.route('/chart-fields', methods=['GET'])
def get_chart_fields():
    """Return the list of fields available for chart axes."""
    fields = [
        {'key': key, 'label': meta['label'], 'type': meta['type']}
        for key, meta in FIELD_REGISTRY.items()
    ]
    return jsonify({'fields': fields})
```

- [ ] **Step 2: Register the blueprint in app.py**

Open `backend/app.py`. Find where other blueprints are registered (look for lines like `from blueprints.chart import chart` and `app.register_blueprint(chart)`). Add after the last blueprint registration:

```python
from blueprints.chart_fields import chart_fields_bp
app.register_blueprint(chart_fields_bp)
```

- [ ] **Step 3: Verify the endpoint responds**

With the backend running (or via `flask run`), test:
```bash
curl http://localhost:5000/api/chart-fields
```
Expected: JSON with a `fields` array containing at least 12 entries, each with `key`, `label`, `type`.

- [ ] **Step 4: Commit**

```bash
git add backend/blueprints/chart_fields.py backend/app.py
git commit -m "feat: add GET /api/chart-fields registry endpoint"
```

---

### Task 2: Backend — chart data query endpoint

**Files:**
- Modify: `backend/blueprints/chart_fields.py`

**Interfaces:**
- Consumes: `FIELD_REGISTRY` from Task 1
- Consumes: `GET /api/filters` (existing) — the filter criteria are already stored in Redis under `stored_filters:{user_id}`
- Produces: `POST /api/chart-data` with body `{ filter_id: string, x_field: string, y_field: string }` → `{ x: (number|string)[], y: (number|string)[] }`

- [ ] **Step 1: Add the data-fetching helper functions to chart_fields.py**

Append to `backend/blueprints/chart_fields.py`:

```python
def _get_patient_ids_for_filter(filter_id):
    """Return a list of patient UUIDs that match the stored filter criteria."""
    from blueprints.filters import get_stored_filters
    from db_loading.generate_display_nifti import get_filtered_tumor_ids  # noqa: reuse existing filter logic
    # get_stored_filters returns dict keyed by filter_id
    stored = get_stored_filters()
    if filter_id not in stored:
        # default: all patients
        from models import Patients
        return [str(p.id) for p in Patients.query.with_entities(Patients.id).all()]
    criteria = stored[filter_id].get('criteria', {})
    # Reuse existing filter plumbing from generate_display_nifti to get matching patients.
    # It returns NIfTI IDs; we need patient IDs instead.
    # Query patients directly using same demographic criteria subset.
    q = Patients.query
    demo = criteria.get('patient_demographics', {})
    if demo.get('sex'):
        q = q.filter(Patients.sex.in_(demo['sex']))
    if demo.get('origin_cancer'):
        q = q.filter(Patients.origin_cancer.in_(demo['origin_cancer']))
    # age_range, height_range, weight_range are stored as FilterOption {label, min, max} lists
    for field_name, db_col in [
        ('age_range', None),  # handled separately via dob
        ('height_range', Patients.height_cm),
        ('weight_range', Patients.weight_kg),
        ('tumor_count_range', Patients.tumor_count),
    ]:
        opts = demo.get(field_name, [])
        if opts and field_name != 'age_range':
            for opt in opts:
                if isinstance(opt, dict):
                    if opt.get('min') is not None:
                        q = q.filter(db_col >= opt['min'])
                    if opt.get('max') is not None:
                        q = q.filter(db_col <= opt['max'])
    clinical = criteria.get('clinical_data', {})
    for field_name, db_col in [
        ('systolic_bp_range', Patients.systolic_bp),
        ('diastolic_bp_range', Patients.diastolic_bp),
    ]:
        opts = clinical.get(field_name, [])
        for opt in opts:
            if isinstance(opt, dict):
                if opt.get('min') is not None:
                    q = q.filter(db_col >= opt['min'])
                if opt.get('max') is not None:
                    q = q.filter(db_col <= opt['max'])
    return [str(p.id) for p in q.with_entities(Patients.id).all()]


def _fetch_field_values(field_key, patient_ids):
    """Return a list of values for the given field across the provided patient IDs."""
    if not patient_ids:
        return []
    meta = FIELD_REGISTRY.get(field_key)
    if not meta:
        return []
    table = meta['table']

    if table == 'patient':
        rows = Patients.query.filter(Patients.id.in_(patient_ids)).all()
        if field_key == 'patient_age':
            today = datetime.date.today()
            return [today.year - p.dob.year - ((today.month, today.day) < (p.dob.month, p.dob.day)) for p in rows]
        attr_map = {
            'patient_height_cm': 'height_cm',
            'patient_weight_kg': 'weight_kg',
            'patient_systolic_bp': 'systolic_bp',
            'patient_diastolic_bp': 'diastolic_bp',
            'patient_tumor_count': 'tumor_count',
            'patient_sex': 'sex',
            'patient_origin_cancer': 'origin_cancer',
        }
        attr = attr_map.get(field_key)
        return [getattr(p, attr) for p in rows] if attr else []

    if table == 'tumor':
        rows = (
            TumorMask.query
            .join(NiftiData, TumorMask.id == NiftiData.id)
            .filter(NiftiData.patient_id.in_(patient_ids))
            .all()
        )
        if field_key == 'tumor_volume_mm3':
            return [r.volume_mm3 for r in rows]
        if field_key == 'tumor_location':
            return [r.location for r in rows]

    if table == 'dose':
        rows = (
            DoseMask.query
            .join(NiftiData, DoseMask.id == NiftiData.id)
            .filter(NiftiData.patient_id.in_(patient_ids))
            .all()
        )
        if field_key == 'dose_max_dose':
            return [r.max_dose for r in rows]
        if field_key == 'dose_volume_mm3':
            return [r.volume_mm3 for r in rows]

    return []
```

- [ ] **Step 2: Add the POST /api/chart-data endpoint**

Append to `backend/blueprints/chart_fields.py`:

```python
@chart_fields_bp.route('/chart-data', methods=['POST'])
def get_chart_data():
    """Fetch x and y value arrays for two chosen fields, scoped to a filter."""
    body = request.get_json(silent=True) or {}
    filter_id = body.get('filter_id', 'default_id')
    x_field = body.get('x_field')
    y_field = body.get('y_field')

    if not x_field or not y_field:
        return jsonify({'error': 'x_field and y_field are required'}), 400
    if x_field not in FIELD_REGISTRY or y_field not in FIELD_REGISTRY:
        return jsonify({'error': 'unknown field key'}), 400

    patient_ids = _get_patient_ids_for_filter(filter_id)
    x_values = _fetch_field_values(x_field, patient_ids)
    y_values = _fetch_field_values(y_field, patient_ids)

    # For scatter/line: pair rows. For cross-table fields, pair by positional index
    # (lengths may differ when mixing patient vs. tumor fields).
    return jsonify({'x': x_values, 'y': y_values})
```

- [ ] **Step 3: Add the request import at the top of chart_fields.py**

Make sure `request` is imported. The top of the file should be:
```python
from flask import Blueprint, jsonify, request
```

- [ ] **Step 4: Test the endpoint**

With the backend running:
```bash
curl -X POST http://localhost:5000/api/chart-data \
  -H "Content-Type: application/json" \
  -d '{"filter_id": "default_id", "x_field": "patient_height_cm", "y_field": "patient_weight_kg"}'
```
Expected: `{"x": [...], "y": [...]}` with numeric arrays (can be empty if DB has no patients, but no 500 error).

- [ ] **Step 5: Commit**

```bash
git add backend/blueprints/chart_fields.py
git commit -m "feat: add POST /api/chart-data for DB-driven chart field values"
```

---

### Task 3: Frontend — field-picker UI in NewChartModal

**Files:**
- Modify: `frontend/src/components/NewChartModal.tsx`

**Interfaces:**
- Consumes: `GET /api/chart-fields` → `{ fields: { key: string; label: string; type: string }[] }`
- Consumes: `POST /api/chart-data` → `{ x: any[], y: any[] }`
- Consumes: existing `POST /api/charts` (unchanged)

- [ ] **Step 1: Add state for field definitions and selected fields**

Inside the `NewChartModal` component, after the existing state declarations, add:

```typescript
const [fieldDefs, setFieldDefs] = useState<{ key: string; label: string; type: string }[]>([]);
const [selectedXField, setSelectedXField] = useState<string>('');
const [selectedYField, setSelectedYField] = useState<string>('');
const [isFetchingData, setIsFetchingData] = useState(false);
```

- [ ] **Step 2: Fetch field definitions when modal opens**

Add a new `useEffect` after the existing filters fetch `useEffect`:

```typescript
useEffect(() => {
  if (isOpen) {
    fetch('/api/chart-fields')
      .then((r) => r.json())
      .then((data) => setFieldDefs(data.fields || []))
      .catch((e) => console.error('Error fetching chart fields:', e));
  }
}, [isOpen]);
```

- [ ] **Step 3: Replace the Series Data text inputs with field pickers**

Find the "Series Data" section (the block starting with `<div className='mb-4'>` that contains `seriesData.map(...)`). Replace the entire Series Data block with:

```typescript
{/* Field Selection */}
<div className='mb-4'>
  <label className='block text-sm font-medium text-gray-700 mb-1'>X Axis Field</label>
  <select
    value={selectedXField}
    onChange={(e) => setSelectedXField(e.target.value)}
    className='w-full border border-gray-300 rounded p-2'
  >
    <option value="">Select a field…</option>
    {fieldDefs.map((f) => (
      <option key={f.key} value={f.key}>{f.label}</option>
    ))}
  </select>
</div>

<div className='mb-4'>
  <label className='block text-sm font-medium text-gray-700 mb-1'>Y Axis Field</label>
  <select
    value={selectedYField}
    onChange={(e) => setSelectedYField(e.target.value)}
    className='w-full border border-gray-300 rounded p-2'
  >
    <option value="">Select a field…</option>
    {fieldDefs.map((f) => (
      <option key={f.key} value={f.key}>{f.label}</option>
    ))}
  </select>
</div>
```

- [ ] **Step 4: Update the createChart function**

Replace the entire `createChart` function:

```typescript
const createChart = async () => {
  if (!selectedChartType || !selectedXField || !selectedYField) return;
  setIsFetchingData(true);
  try {
    // 1. Fetch field data from the backend for the active filter
    const dataRes = await fetch('/api/chart-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({
        filter_id: selectedFilter || 'default_id',
        x_field: selectedXField,
        y_field: selectedYField,
      }),
    });
    if (!dataRes.ok) {
      console.error('Failed to fetch chart data');
      return;
    }
    const { x, y } = await dataRes.json();

    // 2. Build chart payload using the resolved data
    const chartId = crypto.randomUUID();
    const xLabel = fieldDefs.find((f) => f.key === selectedXField)?.label || selectedXField;
    const yLabel = fieldDefs.find((f) => f.key === selectedYField)?.label || selectedYField;

    const chartData = {
      id: chartId,
      type: selectedChartType,
      title: chartSettings.title || `${xLabel} vs ${yLabel}`,
      data: {
        xaxis_title: chartSettings.xaxis_title || xLabel,
        yaxis_title: chartSettings.yaxis_title || yLabel,
        series: [
          {
            name: 'Data',
            trace: { x, y },
          },
        ],
      },
    };

    // 3. POST to charts endpoint (unchanged format)
    const chartRes = await fetch('/api/charts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(chartData),
    });
    if (!chartRes.ok) {
      console.error('Failed to create chart');
      return;
    }
    const config = await chartRes.json();
    onChartCreated(chartId, config);
    closeModal();
  } catch (e) {
    console.error('Error creating chart:', e);
  } finally {
    setIsFetchingData(false);
  }
};
```

- [ ] **Step 5: Update the Create Chart button disabled state and loading indicator**

Replace the Create Chart `<button>` at the bottom of the modal:

```typescript
<button
  onClick={createChart}
  disabled={!selectedChartType || !selectedXField || !selectedYField || isFetchingData}
  className={`px-4 py-2 bg-[#2774AE] text-white rounded-md transition-colors text-sm flex items-center gap-2 ${
    !selectedChartType || !selectedXField || !selectedYField || isFetchingData
      ? 'opacity-50 cursor-not-allowed'
      : 'hover:bg-blue-700'
  }`}
>
  {isFetchingData && (
    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
    </svg>
  )}
  {isFetchingData ? 'Loading data…' : 'Create Chart'}
</button>
```

- [ ] **Step 6: Update the resetForm function to clear new state**

Add to `resetForm`:
```typescript
setSelectedXField('');
setSelectedYField('');
setIsFetchingData(false);
```

- [ ] **Step 7: Remove the now-unused seriesData state and helpers**

Delete the following from `NewChartModal.tsx` (they are replaced by the field picker):
- `const [seriesData, setSeriesData] = useState<SeriesData[]>([...]);`
- `const handleSeriesChange = ...`
- `const addSeries = ...`
- `const removeSeries = ...`
- The `SeriesData` interface

Also remove `seriesData` references from `resetForm`.

- [ ] **Step 8: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -40
```
Expected: zero errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/NewChartModal.tsx
git commit -m "feat: replace manual chart data entry with DB field pickers in NewChartModal"
```
