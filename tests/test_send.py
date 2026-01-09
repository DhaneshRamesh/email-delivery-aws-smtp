"""Tests for the send routes."""
from __future__ import annotations

import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.routes.send import SendTestRequest, send_test_email
from src.db import models
from src.services import ses


def test_send_test_email(monkeypatch):
    def mock_send_email(**kwargs):  # type: ignore[override]
        return "test-message-id"

    monkeypatch.setattr(ses.ses_service, "send_email", mock_send_email)

    engine = create_engine("sqlite:///:memory:", future=True)
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    request = SendTestRequest(
        recipient="alice@example.com",
        subject="Hello",
        body="Test",
    )
    response = asyncio.run(send_test_email(request, db=db))
    assert response.message_id == "test-message-id"
    assert response.queued is False
