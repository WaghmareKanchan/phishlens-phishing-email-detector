"""Test setup: throw-away DB + empty artifacts dir, configured BEFORE the app is imported."""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="phishlens_test_"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_TMP / 'test.db'}",
    "SECRET_KEY": "test-secret-key-not-for-production",
    "BCRYPT_ROUNDS": "4",
    "ENV": "development",
    "ARTIFACTS_DIR": str(_TMP / "artifacts"),
    "CORS_ORIGINS": "",
})
(_TMP / "artifacts").mkdir()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.rate_limit import ALL_LIMITERS  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:     # `with` runs the lifespan (creates tables, loads models)
        yield c


@pytest.fixture(autouse=True)
def _reset_limiters():
    for lim in ALL_LIMITERS:
        lim.clear()


_counter = {"n": 0}


def make_user(client, name="Test User", password="Password123"):
    _counter["n"] += 1
    email = f"user{_counter['n']}@example.com"
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    d = r.json()
    return {"email": email, "password": password, "token": d["access_token"], "user": d["user"],
            "h": {"Authorization": "Bearer " + d["access_token"]}}


@pytest.fixture(scope="session")
def admin(client):
    """First account ever created -> admin. Session scoped and requested first by the tests that need it."""
    return make_user(client, "Admin Person")


@pytest.fixture
def user(client, admin):   # `admin` first so that it really is the first account
    return make_user(client)
