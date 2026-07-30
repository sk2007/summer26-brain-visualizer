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
