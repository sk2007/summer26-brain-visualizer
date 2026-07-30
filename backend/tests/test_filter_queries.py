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
