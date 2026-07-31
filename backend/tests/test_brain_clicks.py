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
