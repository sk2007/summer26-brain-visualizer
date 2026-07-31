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


def test_create_persists_to_db_and_appears_in_get(client, app, fake_redis):
    from models import SavedChart

    chart_id = str(uuid.uuid4())
    resp = client.post("/api/charts", json=_line_chart_payload(chart_id))
    assert resp.status_code == 200

    # Appears in GET
    get_data = client.get("/api/charts").get_json()
    assert chart_id in get_data

    # Written to DB — query inside app context (required outside a request)
    with app.app_context():
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


def test_charts_are_scoped_per_user(app, fake_redis):
    from tests.conftest import set_session_user

    client_a = app.test_client()
    client_b = app.test_client()
    set_session_user(client_a, "user-a")
    set_session_user(client_b, "user-b")

    chart_id = str(uuid.uuid4())
    client_a.post("/api/charts", json=_line_chart_payload(chart_id))

    # User A still sees their own chart (the write was scoped to A, not dropped).
    a_data = client_a.get("/api/charts").get_json()
    assert chart_id in a_data

    # User B must not see user A's chart (B falls back to defaults).
    b_data = client_b.get("/api/charts").get_json()
    assert chart_id not in b_data
    assert set(b_data.keys()) == {"1", "2", "3", "4", "5", "6"}


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


def test_defaults_never_written_to_db_after_save(client, app, fake_redis):
    import uuid
    from models import SavedChart
    chart_id = str(uuid.uuid4())
    client.post("/api/charts", json=_line_chart_payload(chart_id))
    # Only the user chart is persisted; no default IDs in the DB.
    with app.app_context():
        ids = {c.id for c in SavedChart.query.all()}
    assert ids == {chart_id}
