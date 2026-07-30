# Backend Test Suite + CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the project's first automated backend test suite (pytest) covering chart persistence and filter/chart-data query logic, plus a CI job that runs it against a real Postgres on every pull request.

**Architecture:** A `backend/tests/` pytest package runs against a throwaway `brain_test` Postgres database with Redis faked in-memory. No changes to `app.py` or the blueprints. A session-scoped fixture sets `DATABASE_URL` to the test DB *before* importing `app` (the app builds `db` at import time, so import order is load-bearing), ensures `brain_test` exists, and creates tables. Per-test isolation is by table truncation (the app code commits mid-request, which would defeat a rollback scheme). Blueprints use lazy `from app import redis_cache` imports, so monkeypatching `app.redis_cache` with a dict-backed fake is picked up on the next call.

**Tech Stack:** Python 3.11, Flask, Flask-SQLAlchemy, PostgreSQL, pytest, GitHub Actions.

## Global Constraints

- Tests-only change: **no edits** to `app.py` or any file under `backend/blueprints/`. The diff is limited to `backend/tests/`, `backend/pytest.ini`, `backend/requirements-dev.txt`, and `.github/workflows/backend-tests.yml`.
- Tests must run against **real Postgres**, never SQLite (query logic uses a `JSON` column and `db.extract('year', ...)`).
- The test database name must contain **`brain_test`**; never point tests at `brain_dev`. Fail loudly if the resolved URL is not the test DB before any `drop_all`.
- **No bug fixes.** Tests assert current *correct* behavior. If a test would surface a genuine bug, omit that case or mark it `xfail` with a comment — do not assert buggy behavior as correct, and do not fix the bug in this PR.
- Dependency floor: add only `pytest` and `pytest-cov`. No `factory_boy`, no `fakeredis` — the Redis fake and seed helpers are hand-rolled.
- `DATABASE_URL` for tests defaults to `postgresql://myuser:mypassword@localhost:5432/brain_test`, overridable via `TEST_DATABASE_URL`.

---

### Task 1: Test harness scaffolding + smoke test

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_smoke.py`

**Interfaces:**
- Produces (used by Tasks 2 & 3):
  - `client` fixture → `flask.testing.FlaskClient` bound to the test app.
  - `fake_redis` fixture → object with `get_path(key)`, `set_path(key, value)`, `delete_path(key)`, `path_exists(key)`, and `clear()`; also installed as `app.redis_cache`.
  - autouse `clean_tables` fixture → deletes all rows after each test.
  - `app` fixture (session) → the imported Flask `app`, bound to `brain_test`, tables created.

- [ ] **Step 1: Create the dev requirements file**

Create `backend/requirements-dev.txt`:

```
pytest==8.3.4
pytest-cov==6.0.0
```

- [ ] **Step 2: Create pytest.ini**

Create `backend/pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v
```

- [ ] **Step 3: Create the tests package marker**

Create `backend/tests/__init__.py` as an empty file.

- [ ] **Step 4: Write conftest.py**

Create `backend/tests/conftest.py`. This sets the test DB URL **before** importing `app`, ensures the database exists, creates tables once per session, installs the in-memory Redis fake, and truncates tables between tests.

```python
import os
import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

# --- Resolve the test database URL and guard it, BEFORE importing app ---------
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://myuser:mypassword@localhost:5432/brain_test",
)
if "brain_test" not in TEST_DATABASE_URL:
    raise RuntimeError(
        f"Refusing to run tests against a non-test database: {TEST_DATABASE_URL}"
    )

# app.py reads DATABASE_URL at import time and binds `db` to it. Must be set now.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def _ensure_database_exists(db_url: str) -> None:
    """Create the target database if it does not already exist."""
    url = make_url(db_url)
    db_name = url.database
    admin_url = url.set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    engine.dispose()


class FakeRedis:
    """In-memory stand-in for RedisCache (get_path/set_path/delete_path/path_exists)."""

    def __init__(self):
        self._store = {}

    def get_path(self, key):
        return self._store.get(key)

    def set_path(self, key, path):
        self._store[key] = path

    def delete_path(self, key):
        self._store.pop(key, None)

    def path_exists(self, key):
        return key in self._store

    def clear(self):
        self._store.clear()


@pytest.fixture(scope="session")
def app():
    _ensure_database_exists(TEST_DATABASE_URL)

    import app as app_module  # binds db to brain_test via DATABASE_URL set above
    flask_app = app_module.app
    flask_app.config["TESTING"] = True

    import models  # noqa: F401  (ensure all models are registered)
    from app import db

    with flask_app.app_context():
        # Guard again at runtime before touching the schema.
        assert "brain_test" in str(db.engine.url), "Not bound to the test database!"
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.drop_all()


@pytest.fixture()
def fake_redis(app, monkeypatch):
    """Replace app.redis_cache with an in-memory fake for the duration of a test."""
    import app as app_module
    fake = FakeRedis()
    monkeypatch.setattr(app_module, "redis_cache", fake)
    return fake


@pytest.fixture(autouse=True)
def clean_tables(app):
    """Delete all rows after each test, FK-safe (children before parents)."""
    yield
    from app import db
    with app.app_context():
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture()
def client(app):
    return app.test_client()


def set_session_user(client, user_id):
    """Pin a session user_id on a test client so per-user scoping is deterministic."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
```

- [ ] **Step 5: Write the smoke test**

Create `backend/tests/test_smoke.py`. It proves the harness works end to end: the DB round-trips a row and the Redis fake is installed.

```python
import datetime


def test_database_roundtrip(app):
    """A Patients row can be inserted and read back — proves DB binding works."""
    from app import db
    from models import Patients

    with app.app_context():
        p = Patients(
            origin_cancer="lung",
            tumor_count=2,
            dob=datetime.date(1980, 1, 1),
            sex="F",
            height_cm=165.0,
            weight_kg=60.0,
            systolic_bp=120,
            diastolic_bp=80,
            date_of_original_diagnosis=datetime.date(2020, 1, 1),
            date_of_metastatic_diagnosis=datetime.date(2021, 1, 1),
        )
        db.session.add(p)
        db.session.commit()
        assert Patients.query.count() == 1


def test_fake_redis_installed(fake_redis):
    """The Redis fake is wired into app.redis_cache and round-trips values."""
    import app as app_module
    assert app_module.redis_cache is fake_redis
    fake_redis.set_path("k", "v")
    assert fake_redis.get_path("k") == "v"


def test_tables_are_clean_between_tests(app):
    """clean_tables truncated the Patients row from the previous test."""
    from models import Patients
    with app.app_context():
        assert Patients.query.count() == 0
```

- [ ] **Step 6: Run the smoke test**

Ensure Postgres is reachable on `localhost:5432` (the docker-compose `db` service exposes it). Then:

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && \
  pip install -r requirements.txt -r requirements-dev.txt && \
  python -m pytest tests/test_smoke.py -v
```

Expected: 3 passed. `test_tables_are_clean_between_tests` confirms truncation ran; `test_fake_redis_installed` confirms the monkeypatch.

If import of `app` fails on a missing dependency, install `backend/requirements.txt` first (as shown). If Postgres is not running, start it with `docker-compose up -d db` from the repo root.

- [ ] **Step 7: Commit**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && \
git add backend/requirements-dev.txt backend/pytest.ini backend/tests/__init__.py \
        backend/tests/conftest.py backend/tests/test_smoke.py && \
git commit -m "test: add pytest harness (real Postgres + fake Redis) and smoke tests"
```

---

### Task 2: Chart persistence tests

**Files:**
- Create: `backend/tests/test_chart_persistence.py`

**Interfaces:**
- Consumes: `client`, `fake_redis`, `set_session_user` from `conftest.py` (Task 1).
- Consumes (production code under test): `POST /api/charts`, `GET /api/charts`, `DELETE /api/charts/<id>` in `backend/blueprints/chart.py`; the `SavedChart` model in `backend/models.py`.

**Context:** `GET /api/charts` returns a dict of *rendered plotly configs* keyed by chart id (not the raw stored dict). With an empty cache and empty DB it returns the six default charts keyed `"1"`–`"6"`. `POST /api/charts` stores the chart (Redis always; DB for non-default ids) and returns the rendered config. `create_chart` rejects an id that collides with a default id (`"1"`–`"6"`) with HTTP 400. The chart payload must be a shape the chart creators can render — reuse the default line-chart shape.

- [ ] **Step 1: Write the chart-persistence tests**

Create `backend/tests/test_chart_persistence.py`:

```python
import uuid

# A valid line-chart payload the chart creators can render.
def _line_chart_payload(chart_id):
    return {
        "id": chart_id,
        "type": "line_chart",
        "title": "Test Chart",
        "data": {
            "xaxis_title": "Time",
            "yaxis_title": "Value",
            "series": [
                {
                    "name": "Series 1",
                    "mode": "lines",
                    "trace": {"x": [1, 2, 3], "y": [10, 15, 20]},
                    "traceType": "line_chart_trace",
                }
            ],
        },
    }


def test_empty_state_returns_six_defaults(client, fake_redis):
    resp = client.get("/api/charts")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {"1", "2", "3", "4", "5", "6"}


def test_create_persists_to_db_and_appears_in_get(client, fake_redis):
    from models import SavedChart

    chart_id = str(uuid.uuid4())
    resp = client.post("/api/charts", json=_line_chart_payload(chart_id))
    assert resp.status_code == 200

    # Appears in GET
    get_data = client.get("/api/charts").get_json()
    assert chart_id in get_data

    # Written to DB
    assert SavedChart.query.filter_by(id=chart_id).first() is not None
    # Defaults are never written to DB
    assert SavedChart.query.filter(SavedChart.id.in_(["1", "2", "3"])).count() == 0


def test_cache_miss_rehydrates_from_db(client, fake_redis):
    chart_id = str(uuid.uuid4())
    client.post("/api/charts", json=_line_chart_payload(chart_id))

    # Force a cache miss
    fake_redis.clear()

    get_data = client.get("/api/charts").get_json()
    assert chart_id in get_data
    # Cache was re-warmed (some stored_charts:* key now exists)
    assert any(k.startswith("stored_charts:") for k in fake_redis._store)


def test_delete_is_durable_across_cache_miss(client, fake_redis):
    chart_id = str(uuid.uuid4())
    client.post("/api/charts", json=_line_chart_payload(chart_id))

    del_resp = client.delete(f"/api/charts/{chart_id}")
    assert del_resp.status_code == 200

    # Clear cache: if the chart still lived in the DB it would resurrect here.
    fake_redis.clear()
    get_data = client.get("/api/charts").get_json()
    assert chart_id not in get_data
    # With the DB empty again, defaults are returned.
    assert set(get_data.keys()) == {"1", "2", "3", "4", "5", "6"}


def test_create_with_default_id_is_rejected(client, fake_redis):
    resp = client.post("/api/charts", json=_line_chart_payload("1"))
    assert resp.status_code == 400
    # Defaults remain intact and uncorrupted.
    get_data = client.get("/api/charts").get_json()
    assert set(get_data.keys()) == {"1", "2", "3", "4", "5", "6"}


def test_charts_are_scoped_per_user(app, fake_redis):
    from tests.conftest import set_session_user

    client_a = app.test_client()
    client_b = app.test_client()
    set_session_user(client_a, "user-a")
    set_session_user(client_b, "user-b")

    chart_id = str(uuid.uuid4())
    client_a.post("/api/charts", json=_line_chart_payload(chart_id))

    # User B must not see user A's chart (B falls back to defaults).
    b_data = client_b.get("/api/charts").get_json()
    assert chart_id not in b_data
    assert set(b_data.keys()) == {"1", "2", "3", "4", "5", "6"}
```

- [ ] **Step 2: Run the chart-persistence tests**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && \
  python -m pytest tests/test_chart_persistence.py -v
```

Expected: 6 passed.

If `test_charts_are_scoped_per_user` fails on import of `set_session_user`, confirm `backend/pytest.ini` sets `testpaths = tests` and run pytest from the `backend/` directory so `tests` is importable as a package.

- [ ] **Step 3: Commit**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && \
git add backend/tests/test_chart_persistence.py && \
git commit -m "test: cover chart persistence (defaults, DB sync, cache miss, delete, scoping)"
```

---

### Task 3: Filter query + chart-data tests

**Files:**
- Create: `backend/tests/seed.py`
- Create: `backend/tests/test_filter_queries.py`

**Interfaces:**
- Consumes: `client`, `fake_redis`, `app` from `conftest.py` (Task 1).
- Consumes (production code under test): `_get_patient_ids_for_filter(filter_id)` and `POST /api/chart-data` in `backend/blueprints/chart_fields.py`; `get_stored_filters()` in `backend/blueprints/filters.py` (reads `stored_filters:{user_id}` from Redis); models `Patients`, `NiftiData`, `TumorMask`, `DoseMask`.
- Produces (used within this task): `seed.py` helpers — `seed_patient(**overrides) -> Patients`, `seed_tumor(patient, location, volume_mm3) -> TumorMask`, `seed_dose(patient, max_dose) -> DoseMask`, `seed_filter(fake_redis, user_id, filter_id, criteria) -> None`.

**Context on how filters are read:** `_get_patient_ids_for_filter` calls `get_stored_filters()`, which reads the Redis key `stored_filters:{session['user_id']}` and returns `{filter_id: {"name": ..., "criteria": {...}}}`. Tests seed that key in the fake Redis directly (no `POST /api/filters`, which would trigger NIfTI generation). Direct-call tests run inside `app.test_request_context()` with `session["user_id"]` set, so both the seeded key and the query use the same user id. `_get_patient_ids_for_filter` returns a list of `str(patient.id)`.

**Context on the schema:** A tumor/dose mask row requires a parent `NiftiData` row with a matching `id` and a `series_type` of `'tumor_mask'`/`'dose_mask'`. `TumorMask` and `DoseMask` have many NOT-NULL geometry columns (`x_com`…`z_max`); the seed helpers fill them with zeros. `DoseMask.max_dose` is an Integer.

- [ ] **Step 1: Write the seed helpers**

Create `backend/tests/seed.py`:

```python
import datetime
import uuid


def seed_patient(**overrides):
    """Insert and return a Patients row. Sensible defaults, override any field."""
    from app import db
    from models import Patients

    fields = dict(
        origin_cancer="lung",
        tumor_count=1,
        dob=datetime.date(1980, 1, 1),
        sex="F",
        height_cm=165.0,
        weight_kg=60.0,
        systolic_bp=120,
        diastolic_bp=80,
        date_of_original_diagnosis=datetime.date(2020, 1, 1),
        date_of_metastatic_diagnosis=datetime.date(2021, 1, 1),
    )
    fields.update(overrides)
    p = Patients(**fields)
    db.session.add(p)
    db.session.commit()
    return p


_GEOM = dict(
    x_com=0, y_com=0, z_com=0,
    x_min=0, x_max=1, y_min=0, y_max=1, z_min=0, z_max=1,
)


def seed_tumor(patient, location, volume_mm3):
    """Create a NiftiData(tumor_mask) + TumorMask pair for a patient."""
    from app import db
    from models import NiftiData, TumorMask

    nid = uuid.uuid4()
    db.session.add(NiftiData(id=nid, patient_id=patient.id, series_type="tumor_mask"))
    db.session.add(TumorMask(id=nid, location=location, volume_mm3=volume_mm3, **_GEOM))
    db.session.commit()


def seed_dose(patient, max_dose, volume_mm3=100.0):
    """Create a NiftiData(dose_mask) + DoseMask pair for a patient."""
    from app import db
    from models import NiftiData, DoseMask

    nid = uuid.uuid4()
    db.session.add(NiftiData(id=nid, patient_id=patient.id, series_type="dose_mask"))
    db.session.add(DoseMask(id=nid, max_dose=max_dose, volume_mm3=volume_mm3, **_GEOM))
    db.session.commit()


def seed_filter(fake_redis, user_id, filter_id, criteria):
    """Write a stored filter into the fake Redis under this user's key."""
    import json
    payload = {filter_id: {"name": "Test Filter", "criteria": criteria}}
    fake_redis.set_path(f"stored_filters:{user_id}", json.dumps(payload))
```

- [ ] **Step 2: Write the filter-selection tests (direct function call)**

Create `backend/tests/test_filter_queries.py` with the selection tests. Each runs inside a request context with a fixed `user_id`, seeds a filter into the fake Redis, and asserts on the returned patient-id set.

**Note on detached instances:** Flask-SQLAlchemy commits with
`expire_on_commit=True`, so a model instance's attributes are *expired* after
`commit()` and accessing `patient.id` *outside* an app context raises
`DetachedInstanceError`. Every `str(patient.id)` used in an assertion is
therefore captured **inside** the `with app.app_context()` block that seeded it.

```python
import datetime

from tests.seed import seed_patient, seed_tumor, seed_dose, seed_filter

USER = "filter-user"


def _ids_for(app, fake_redis, filter_id, criteria):
    """Seed the filter and call _get_patient_ids_for_filter within a request ctx."""
    from flask import session
    from blueprints.chart_fields import _get_patient_ids_for_filter

    with app.test_request_context("/"):
        session["user_id"] = USER
        seed_filter(fake_redis, USER, filter_id, criteria)
        return set(_get_patient_ids_for_filter(filter_id))


def test_unknown_filter_returns_all_patients(app, fake_redis):
    from flask import session
    from blueprints.chart_fields import _get_patient_ids_for_filter

    with app.app_context():
        p1 = seed_patient()
        p2 = seed_patient()
        expected = {str(p1.id), str(p2.id)}

    with app.test_request_context("/"):
        session["user_id"] = USER
        assert set(_get_patient_ids_for_filter("no-such-id")) == expected


def test_sex_filter(app, fake_redis):
    with app.app_context():
        female_id = str(seed_patient(sex="F").id)
        seed_patient(sex="M")
    result = _ids_for(app, fake_redis, "f1", {"patient_demographics": {"sex": ["F"]}})
    assert result == {female_id}


def test_origin_cancer_filter(app, fake_redis):
    with app.app_context():
        lung_id = str(seed_patient(origin_cancer="lung").id)
        seed_patient(origin_cancer="breast")
    result = _ids_for(
        app, fake_redis, "f1",
        {"patient_demographics": {"origin_cancer": ["lung"]}},
    )
    assert result == {lung_id}


def test_age_range_or_union(app, fake_redis):
    # birth years relative to today: -40 and -70 match; -55 is excluded.
    cy = datetime.date.today().year
    with app.app_context():
        young_id = str(seed_patient(dob=datetime.date(cy - 40, 6, 15)).id)
        old_id = str(seed_patient(dob=datetime.date(cy - 70, 6, 15)).id)
        seed_patient(dob=datetime.date(cy - 55, 6, 15))  # excluded
    criteria = {
        "patient_demographics": {
            "age_range": [
                {"label": "35-45", "min": 35, "max": 45},
                {"label": "65-75", "min": 65, "max": 75},
            ]
        }
    }
    result = _ids_for(app, fake_redis, "f1", criteria)
    assert result == {young_id, old_id}


def test_range_or_within_field_and_across_fields(app, fake_redis):
    with app.app_context():
        # matches height 150-160 OR 190-200, and weight 50-70
        short_id = str(seed_patient(height_cm=155.0, weight_kg=60.0).id)
        tall_id = str(seed_patient(height_cm=195.0, weight_kg=60.0).id)
        # in a height band but wrong weight => excluded by AND-across-fields
        wrong_weight_id = str(seed_patient(height_cm=155.0, weight_kg=200.0).id)
    criteria = {
        "patient_demographics": {
            "height_range": [
                {"label": "150-160", "min": 150, "max": 160},
                {"label": "190-200", "min": 190, "max": 200},
            ],
            "weight_range": [{"label": "50-70", "min": 50, "max": 70}],
        }
    }
    result = _ids_for(app, fake_redis, "f1", criteria)
    assert result == {short_id, tall_id}
    assert wrong_weight_id not in result


def test_clinical_bp_ranges(app, fake_redis):
    with app.app_context():
        match_id = str(seed_patient(systolic_bp=118, diastolic_bp=78).id)
        seed_patient(systolic_bp=150, diastolic_bp=95)
    criteria = {
        "clinical_data": {
            "systolic_bp_range": [{"label": "110-125", "min": 110, "max": 125}],
            "diastolic_bp_range": [{"label": "70-85", "min": 70, "max": 85}],
        }
    }
    result = _ids_for(app, fake_redis, "f1", criteria)
    assert result == {match_id}


def test_tumor_location_and_volume(app, fake_redis):
    with app.app_context():
        p_frontal = seed_patient()
        seed_tumor(p_frontal, location="frontal", volume_mm3=500.0)
        p_parietal = seed_patient()
        seed_tumor(p_parietal, location="parietal", volume_mm3=500.0)
        frontal_id = str(p_frontal.id)
        parietal_id = str(p_parietal.id)
    # location filter
    loc = _ids_for(
        app, fake_redis, "f1",
        {"tumor_characteristics": {"tumor_location": ["frontal"]}},
    )
    assert loc == {frontal_id}
    # volume filter (both have 500 => both match a 400-600 band)
    vol = _ids_for(
        app, fake_redis, "f2",
        {"tumor_characteristics": {
            "tumor_volume_range": [{"label": "400-600", "min": 400, "max": 600}]}},
    )
    assert vol == {frontal_id, parietal_id}


def test_dose_range(app, fake_redis):
    with app.app_context():
        treated = seed_patient()
        seed_dose(treated, max_dose=60)
        treated_id = str(treated.id)
        untreated = seed_patient()
        seed_dose(untreated, max_dose=10)
    result = _ids_for(
        app, fake_redis, "f1",
        {"treatment_data": {"dose_range": [{"label": "50-70", "min": 50, "max": 70}]}},
    )
    assert result == {treated_id}


def test_cross_category_and_intersection(app, fake_redis):
    with app.app_context():
        both = seed_patient(sex="F")
        seed_dose(both, max_dose=60)
        both_id = str(both.id)
        female_no_dose = seed_patient(sex="F")
        seed_dose(female_no_dose, max_dose=10)
    criteria = {
        "patient_demographics": {"sex": ["F"]},
        "treatment_data": {"dose_range": [{"label": "50-70", "min": 50, "max": 70}]},
    }
    result = _ids_for(app, fake_redis, "f1", criteria)
    assert result == {both_id}
```

- [ ] **Step 3: Run the selection tests**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && \
  python -m pytest tests/test_filter_queries.py -v
```

Expected: 9 passed.

- [ ] **Step 4: Add the `/api/chart-data` endpoint contract tests**

Append to `backend/tests/test_filter_queries.py`:

```python
def test_chart_data_same_table_returns_aligned_arrays(client, fake_redis):
    from tests.conftest import set_session_user
    set_session_user(client, USER)
    # Seed two patients with known height/weight.
    with client.application.app_context():
        seed_patient(height_cm=150.0, weight_kg=50.0)
        seed_patient(height_cm=180.0, weight_kg=90.0)

    resp = client.post("/api/chart-data", json={
        "filter_id": "no-filter",  # unknown => all patients
        "x_field": "patient_height_cm",
        "y_field": "patient_weight_kg",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert sorted(body["x"]) == [150.0, 180.0]
    assert sorted(body["y"]) == [50.0, 90.0]
    assert len(body["x"]) == len(body["y"]) == 2


def test_chart_data_cross_table_pair_is_rejected(client, fake_redis):
    from tests.conftest import set_session_user
    set_session_user(client, USER)
    resp = client.post("/api/chart-data", json={
        "filter_id": "no-filter",
        "x_field": "patient_age",         # patient table
        "y_field": "tumor_volume_mm3",    # tumor table
    })
    assert resp.status_code == 400


def test_chart_data_unknown_field_is_rejected(client, fake_redis):
    from tests.conftest import set_session_user
    set_session_user(client, USER)
    resp = client.post("/api/chart-data", json={
        "filter_id": "no-filter",
        "x_field": "not_a_field",
        "y_field": "patient_weight_kg",
    })
    assert resp.status_code == 400


def test_chart_data_missing_field_is_rejected(client, fake_redis):
    from tests.conftest import set_session_user
    set_session_user(client, USER)
    resp = client.post("/api/chart-data", json={"filter_id": "no-filter"})
    assert resp.status_code == 400


def test_patient_age_values_compute(client, fake_redis):
    from tests.conftest import set_session_user
    set_session_user(client, USER)
    today = datetime.date.today()
    with client.application.app_context():
        seed_patient(dob=today.replace(year=today.year - 30))

    resp = client.post("/api/chart-data", json={
        "filter_id": "no-filter",
        "x_field": "patient_age",
        "y_field": "patient_age",
    })
    assert resp.status_code == 200
    assert resp.get_json()["x"] == [30]
```

- [ ] **Step 5: Run the full filter test module**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && \
  python -m pytest tests/test_filter_queries.py -v
```

Expected: 14 passed.

- [ ] **Step 6: Run the entire suite**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && \
  python -m pytest -v
```

Expected: 23 passed (3 smoke + 6 chart + 14 filter).

- [ ] **Step 7: Commit**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && \
git add backend/tests/seed.py backend/tests/test_filter_queries.py && \
git commit -m "test: cover filter selection logic and /api/chart-data contract"
```

---

### Task 4: CI workflow

**Files:**
- Create: `.github/workflows/backend-tests.yml`

**Interfaces:**
- Consumes: the pytest suite from Tasks 1–3; `backend/requirements.txt` and `backend/requirements-dev.txt`.

**Context:** The existing `.github/workflows/deploy_test.yml` (deploy-on-push-to-main) is left untouched. This new workflow is a separate gate that runs the suite against a Postgres service container on pull requests and pushes.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/backend-tests.yml`:

```yaml
name: Backend Tests

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: myuser
          POSTGRES_PASSWORD: mypassword
          POSTGRES_DB: brain_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U myuser -d brain_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10

    env:
      TEST_DATABASE_URL: postgresql://myuser:mypassword@localhost:5432/brain_test

    steps:
      - name: Check out code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt -r backend/requirements-dev.txt

      - name: Run tests
        working-directory: backend
        run: python -m pytest -v
```

- [ ] **Step 2: Validate the workflow YAML locally**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && \
  python -c "import yaml; yaml.safe_load(open('.github/workflows/backend-tests.yml')); print('YAML OK')"
```

Expected: `YAML OK`.

- [ ] **Step 3: Confirm the exact command CI runs passes locally**

The workflow runs `python -m pytest -v` from `backend/` against a `brain_test` DB. Reproduce it locally (Postgres must be up on 5432):

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/backend && \
  TEST_DATABASE_URL=postgresql://myuser:mypassword@localhost:5432/brain_test \
  python -m pytest -v
```

Expected: 23 passed.

- [ ] **Step 4: Commit**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer && \
git add .github/workflows/backend-tests.yml && \
git commit -m "ci: run backend pytest suite against Postgres on push and PR"
```

---

## Notes for the executor

- **Postgres must be reachable on `localhost:5432`** for every task's test run. From the repo root: `docker-compose up -d db`. The suite auto-creates the `brain_test` database.
- If `import app` pulls in heavy optional dependencies (pycortex, nibabel) that fail to import in a bare environment, install the full `backend/requirements.txt` first — the smoke test in Task 1 will catch this early.
- Keep to the Global Constraints: if any test reveals a real bug, record it as a follow-up (e.g. append to the SDD ledger) and either omit or `xfail` the case — do not fix production code in this PR.
