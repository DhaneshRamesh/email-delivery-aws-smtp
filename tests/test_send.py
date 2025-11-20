"""Tests for the send routes."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import app
from src.services import ses


def test_send_test_email(monkeypatch):
    client = TestClient(app)

    def mock_send_email(**kwargs):  # type: ignore[override]
        return "test-message-id"

    monkeypatch.setattr(ses.ses_service, "send_email", mock_send_email)

    response = client.post(
        "/send/send-test",
        json={
            "recipient": "alice@example.com",
            "subject": "Hello",
            "body": "Test",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message_id"] == "test-message-id"
    assert payload["queued"] is False
