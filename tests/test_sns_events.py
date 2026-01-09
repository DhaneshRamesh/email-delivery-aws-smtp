"""Tests for SNS event handling."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.routes import events
from src.core.config import settings
from src.db import models
from src.utils import sns as sns_utils


def _make_db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _notification_payload(message: dict) -> dict:
    return {
        "Type": "Notification",
        "MessageId": "sns-message-id",
        "TopicArn": "arn:aws:sns:ap-southeast-2:123456789012:ses-events",
        "Message": json.dumps(message),
        "SignatureVersion": "1",
        "Signature": "dGVzdA==",
        "SigningCertURL": "https://sns.ap-southeast-2.amazonaws.com/SimpleNotificationService-test.pem",
    }


def test_verify_sns_signature_happy(monkeypatch):
    payload = _notification_payload({"notificationType": "Delivery", "mail": {"messageId": "mid"}})

    def fake_fetch(url, timeout_seconds):  # noqa: ARG001
        return b"cert"

    def fake_run(args, input_bytes, timeout_seconds):  # noqa: ARG001
        if "x509" in args:
            return SimpleNamespace(returncode=0, stdout=b"PUBKEY")
        return SimpleNamespace(returncode=0, stdout=b"")

    monkeypatch.setattr(sns_utils, "_fetch_url", fake_fetch)
    monkeypatch.setattr(sns_utils, "_run_openssl", fake_run)
    ok, _ = sns_utils.verify_sns_signature(payload, 3)
    assert ok is True


def test_verify_sns_signature_fail(monkeypatch):
    payload = _notification_payload({"notificationType": "Delivery", "mail": {"messageId": "mid"}})

    def fake_fetch(url, timeout_seconds):  # noqa: ARG001
        return b"cert"

    def fake_run(args, input_bytes, timeout_seconds):  # noqa: ARG001
        return SimpleNamespace(returncode=1, stdout=b"")

    monkeypatch.setattr(sns_utils, "_fetch_url", fake_fetch)
    monkeypatch.setattr(sns_utils, "_run_openssl", fake_run)
    ok, _ = sns_utils.verify_sns_signature(payload, 3)
    assert ok is False


def test_subscription_confirmation(monkeypatch):
    db = _make_db_session()

    def fake_confirm(url, timeout_seconds):  # noqa: ARG001
        return True

    monkeypatch.setattr(events, "confirm_subscription", fake_confirm)
    monkeypatch.setattr(settings, "sns_verify_signatures", False)
    monkeypatch.setattr(
        settings, "sns_allowed_topic_arns", ["arn:aws:sns:ap-southeast-2:123456789012:ses-events"]
    )

    payload = {
        "Type": "SubscriptionConfirmation",
        "MessageId": "sns-message-id",
        "TopicArn": "arn:aws:sns:ap-southeast-2:123456789012:ses-events",
        "SubscribeURL": "https://example.com/confirm",
    }
    result = asyncio.run(events.handle_sns_notification(payload, db=db))
    assert result["status"] == "confirmed"


def test_notification_updates_email_log(monkeypatch):
    db = _make_db_session()
    log = models.EmailLog(
        recipient_email="success@simulator.amazonses.com",
        message_id="ses-message-id",
        status="queued",
    )
    db.add(log)
    db.commit()

    monkeypatch.setattr(settings, "sns_verify_signatures", False)
    monkeypatch.setattr(
        settings, "sns_allowed_topic_arns", ["arn:aws:sns:ap-southeast-2:123456789012:ses-events"]
    )

    message = {
        "notificationType": "Delivery",
        "mail": {
            "messageId": "ses-message-id",
            "destination": ["success@simulator.amazonses.com"],
        },
        "delivery": {"timestamp": "2025-12-16T00:00:00.000Z", "smtpResponse": "250 Ok"},
    }
    payload = _notification_payload(message)
    result = asyncio.run(events.handle_sns_notification(payload, db=db))
    assert result["status"] == "delivered"

    refreshed = db.query(models.EmailLog).filter(models.EmailLog.id == log.id).first()
    assert refreshed.status == "delivered"
    events_count = db.query(models.EmailEvent).count()
    assert events_count == 1


def test_event_persisted_without_log(monkeypatch):
    db = _make_db_session()
    monkeypatch.setattr(settings, "sns_verify_signatures", False)
    monkeypatch.setattr(
        settings, "sns_allowed_topic_arns", ["arn:aws:sns:ap-southeast-2:123456789012:ses-events"]
    )

    message = {
        "notificationType": "Bounce",
        "mail": {"messageId": "missing-log"},
        "bounce": {"timestamp": "2025-12-16T00:00:00.000Z", "bounceType": "Permanent"},
    }
    payload = _notification_payload(message)
    result = asyncio.run(events.handle_sns_notification(payload, db=db))
    assert result["status"] == "bounced"
    event = db.query(models.EmailEvent).first()
    assert event is not None
    assert event.email_log_id is None
