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
