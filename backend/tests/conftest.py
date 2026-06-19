"""Test configuration: ensure a fresh database and provide auth helpers."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True, scope="session")
def fresh_database():
    import app.models  # noqa: F401 -- triggers model registration on Base.metadata
    from app.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="session")
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def auth_headers(client):
    resp = client.post("/api/auth/register", json={
        "email": "testuser@savepilot.test",
        "password": "testpass123",
        "display_name": "Test User",
    })
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
