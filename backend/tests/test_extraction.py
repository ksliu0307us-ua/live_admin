"""Tests for the extraction pipeline."""


NETFLIX_TEXT = """Subject: Your Netflix membership is about to renew

Hi there,

Just a heads-up - your Netflix Premium membership will automatically renew.

Plan: Premium (4K Ultra HD)
Monthly price: $22.99
Payment method: Visa ending in 4242

If you'd like to cancel or change your plan, you can do so anytime at netflix.com/account.

Thanks for being a Netflix member!
The Netflix Team"""


def test_extract_netflix(client, auth_headers):
    response = client.post(
        "/api/extract",
        json={"input_text": NETFLIX_TEXT, "input_type": "paste"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()

    assert "extraction" in data
    assert "action_cards" in data

    extraction = data["extraction"]
    assert extraction["merchant"] == "Netflix"
    assert extraction["amount"] == 22.99
    assert extraction["confidence_score"] > 0.5
    assert extraction["document_type"] == "subscription"
    assert extraction["detected_risk"] is not None
    assert extraction["explanation"] is not None


def test_extract_document_type(client, auth_headers):
    response = client.post(
        "/api/extract",
        json={"input_text": NETFLIX_TEXT, "input_type": "paste"},
        headers=auth_headers,
    )
    assert response.json()["extraction"]["document_type"] == "subscription"


def test_extract_unknown_document(client, auth_headers):
    response = client.post(
        "/api/extract",
        json={
            "input_text": "This is a completely random text that has nothing to do with any purchases or subscriptions whatsoever. Just a long paragraph of filler text.",
            "input_type": "paste",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["extraction"]["document_type"] == "unknown"


def test_extract_too_short(client, auth_headers):
    response = client.post(
        "/api/extract",
        json={"input_text": "short", "input_type": "paste"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_list_documents(client, auth_headers):
    response = client.get("/api/documents", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "pages" in data


def test_get_document_not_found(client, auth_headers):
    response = client.get("/api/documents/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404


def test_delete_document(client, auth_headers):
    create_resp = client.post(
        "/api/extract",
        json={"input_text": NETFLIX_TEXT, "input_type": "paste"},
        headers=auth_headers,
    )
    extraction_id = create_resp.json()["extraction"]["id"]

    delete_resp = client.delete(f"/api/documents/{extraction_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/documents/{extraction_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_no_action_card_for_generic_input(client, auth_headers):
    response = client.post(
        "/api/extract",
        json={
            "input_text": "Hello, just wanted to say thanks for a great product. No issues at all. Keep up the good work!",
            "input_type": "paste",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    cards = response.json()["action_cards"]
    assert any(c["action_type"] == "no_action" for c in cards)


def test_duplicate_detection(client, auth_headers):
    text = "Your Netflix membership will auto-renew for $22.99 at netflix.com/account. Cancel anytime before billing date."
    resp1 = client.post("/api/extract", json={"input_text": text, "input_type": "paste"}, headers=auth_headers)
    assert resp1.status_code == 201
    assert resp1.json()["extraction"]["is_duplicate"] is False

    resp2 = client.post("/api/extract", json={"input_text": text, "input_type": "paste"}, headers=auth_headers)
    assert resp2.status_code == 201
    assert resp2.json()["extraction"]["is_duplicate"] is True
