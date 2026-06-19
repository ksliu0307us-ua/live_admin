"""Tests for draft generation."""


NETFLIX_TEXT = """Subject: Your Netflix membership is about to renew

Hi there,

Just a heads-up - your Netflix Premium membership will automatically renew.

Plan: Premium (4K Ultra HD)
Monthly price: $22.99

If you'd like to cancel, visit netflix.com/account.

The Netflix Team"""


def test_generate_draft(client, auth_headers):
    create_resp = client.post(
        "/api/extract",
        json={"input_text": NETFLIX_TEXT, "input_type": "paste"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    cards = create_resp.json()["action_cards"]
    assert len(cards) > 0

    action_id = cards[0]["id"]
    draft_resp = client.post(f"/api/actions/{action_id}/draft", headers=auth_headers)
    assert draft_resp.status_code == 201

    draft = draft_resp.json()
    assert "subject" in draft
    assert "body" in draft
    assert len(draft["body"]) > 50


def test_generate_draft_with_tone(client, auth_headers):
    create_resp = client.post(
        "/api/extract",
        json={"input_text": NETFLIX_TEXT, "input_type": "paste"},
        headers=auth_headers,
    )
    cards = create_resp.json()["action_cards"]
    action_id = cards[0]["id"]

    draft_resp = client.post(
        f"/api/actions/{action_id}/draft",
        json={"tone": "firm"},
        headers=auth_headers,
    )
    assert draft_resp.status_code == 201


def test_generate_draft_not_found(client, auth_headers):
    resp = client.post("/api/actions/nonexistent-id/draft", headers=auth_headers)
    assert resp.status_code == 404


def test_update_draft(client, auth_headers):
    create_resp = client.post(
        "/api/extract",
        json={"input_text": NETFLIX_TEXT, "input_type": "paste"},
        headers=auth_headers,
    )
    cards = create_resp.json()["action_cards"]
    action_id = cards[0]["id"]

    draft_resp = client.post(f"/api/actions/{action_id}/draft", headers=auth_headers)
    draft_id = draft_resp.json()["id"]

    update_resp = client.patch(
        f"/api/drafts/{draft_id}",
        json={"user_edited_body": "Custom edited body", "copied": True},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["user_edited_body"] == "Custom edited body"


def test_action_status_lifecycle(client, auth_headers):
    create_resp = client.post(
        "/api/extract",
        json={"input_text": NETFLIX_TEXT, "input_type": "paste"},
        headers=auth_headers,
    )
    cards = create_resp.json()["action_cards"]
    action_id = cards[0]["id"]
    assert cards[0]["status"] == "new"

    resp = client.patch(f"/api/actions/{action_id}", json={"status": "reviewed"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "reviewed"

    resp = client.patch(
        f"/api/actions/{action_id}",
        json={"status": "completed", "savings_amount": 22.99},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["savings_amount"] == 22.99
    assert resp.json()["completed_at"] is not None


def test_action_reminder(client, auth_headers):
    create_resp = client.post(
        "/api/extract",
        json={"input_text": NETFLIX_TEXT, "input_type": "paste"},
        headers=auth_headers,
    )
    cards = create_resp.json()["action_cards"]
    action_id = cards[0]["id"]

    resp = client.patch(
        f"/api/actions/{action_id}",
        json={"reminder_date": "2026-07-01"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["reminder_date"] == "2026-07-01"


def test_dashboard(client, auth_headers):
    resp = client.get("/api/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_savings" in data
    assert "documents_count" in data
    assert "actions_by_status" in data
    assert "monthly_savings" in data
