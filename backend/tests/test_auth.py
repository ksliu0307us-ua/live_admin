"""Tests for authentication endpoints."""


def test_register(client):
    resp = client.post("/api/auth/register", json={
        "email": "newuser@savepilot.test",
        "password": "password123",
        "display_name": "New User",
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "newuser@savepilot.test"


def test_register_duplicate(client, auth_headers):
    resp = client.post("/api/auth/register", json={
        "email": "testuser@savepilot.test",
        "password": "testpass123",
    })
    assert resp.status_code == 400


def test_register_weak_password(client):
    resp = client.post("/api/auth/register", json={
        "email": "weak@savepilot.test",
        "password": "short",
    })
    assert resp.status_code == 422


def test_login(client, auth_headers):
    resp = client.post("/api/auth/login", json={
        "email": "testuser@savepilot.test",
        "password": "testpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login", json={
        "email": "testuser@savepilot.test",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_me(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "testuser@savepilot.test"


def test_refresh_token(client, auth_headers):
    login_resp = client.post("/api/auth/login", json={
        "email": "testuser@savepilot.test",
        "password": "testpass123",
    })
    refresh_token = login_resp.json()["refresh_token"]

    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_protected_endpoint_no_auth(client):
    resp = client.get("/api/documents")
    assert resp.status_code in (401, 403)


def test_health_no_auth(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
