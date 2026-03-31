"""Shared fixtures for backend tests."""

import tempfile
from pathlib import Path

import pytest

import storyteller.db as db
from server import app as flask_app


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    """Redirect all DB operations to a fresh temporary database."""
    db_path = tmp_path / "test_stories.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    return db_path


@pytest.fixture()
def client():
    """Flask test client wired to the temporary DB."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c
