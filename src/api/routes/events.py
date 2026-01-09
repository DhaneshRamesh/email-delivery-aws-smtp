"""Inbound webhook handlers for SES/SNS notifications."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.db import models
from src.db.session import get_db
from src.core.config import settings
from src.utils.sns import confirm_subscription, dumps_payload, verify_sns_signature
from src.utils.logger import logger

router = APIRouter(prefix="/events", tags=["events"])


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _update_logs(
    db: Session,
    logs: list[models.EmailLog],
    *,
    status_value: str,
    event_type: str,
    event_time: datetime | None,
    smtp_response: str | None,
    bounce_type: str | None,
    bounce_subtype: str | None,
    complaint_type: str | None,
    ses_message_id: str | None,
) -> None:
    for log in logs:
        if ses_message_id and not log.message_id:
            log.message_id = ses_message_id
        log.status = status_value
        log.last_event_type = event_type
        log.last_event_at = event_time or datetime.now(timezone.utc)
        log.last_smtp_response = smtp_response
        log.bounce_type = bounce_type
        log.bounce_subtype = bounce_subtype
        log.complaint_type = complaint_type
        db.add(log)


def _persist_event(
    db: Session,
    *,
    email_log_id: int | None,
    ses_message_id: str | None,
    sns_message_id: str | None,
    event_type: str,
    topic_arn: str | None,
    signature_verified: bool,
    payload: dict,
) -> None:
    if sns_message_id and topic_arn:
        exists = (
            db.query(models.EmailEvent)
            .filter(models.EmailEvent.sns_message_id == sns_message_id, models.EmailEvent.topic_arn == topic_arn)
            .first()
        )
        if exists:
            return
    event = models.EmailEvent(
        email_log_id=email_log_id,
        ses_message_id=ses_message_id,
        sns_message_id=sns_message_id,
        event_type=event_type,
        topic_arn=topic_arn,
        payload_json=dumps_payload(payload),
        signature_verified=signature_verified,
    )
    db.add(event)


def _add_suppression(db: Session, *, tenant_id: int | None, email: str, reason: str) -> None:
    if tenant_id is None:
        logger.warning("No tenant_id available; skipping suppression for %s", email)
        return
    try:
        existing = (
            db.query(models.SuppressedEmail)
            .filter(models.SuppressedEmail.tenant_id == tenant_id, models.SuppressedEmail.email == email)
            .first()
        )
        if existing:
            return
        db.add(models.SuppressedEmail(tenant_id=tenant_id, email=email, reason=reason))
        subscriber = (
            db.query(models.Subscriber)
            .filter(models.Subscriber.tenant_id == tenant_id, models.Subscriber.email == email)
            .first()
        )
        if subscriber:
            subscriber.status = "suppressed"
            db.add(subscriber)
    except Exception:
        logger.exception("Failed to update suppression for %s", email)


@router.post("/sns")
async def handle_sns_notification(payload: dict, db: Session = Depends(get_db)) -> dict[str, str]:
    """Handle SES SNS notifications for bounces/complaints."""
    message_type = payload.get("Type")
    topic_arn = payload.get("TopicArn")
    sns_message_id = payload.get("MessageId")
    logger.info("SNS event received message_id=%s type=%s topic=%s", sns_message_id, message_type, topic_arn)

    if not settings.sns_allowed_topic_arns and settings.environment != "development":
        logger.warning("Rejected SNS message %s because no allowed topics are configured", sns_message_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SNS topics not configured")
    if settings.sns_allowed_topic_arns and topic_arn not in settings.sns_allowed_topic_arns:
        logger.warning("Rejected SNS message %s from topic %s", sns_message_id, topic_arn)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="TopicArn not allowed")

    signature_verified = False
    skip_verification = settings.environment == "development" and settings.sns_skip_signature_verification
    if settings.sns_verify_signatures and not skip_verification:
        verified, reason = verify_sns_signature(payload, settings.sns_signature_timeout_seconds)
        if not verified:
            logger.warning("Rejected SNS message %s: %s", sns_message_id, reason)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid SNS signature")
        signature_verified = True

    if message_type == "SubscriptionConfirmation":
        subscribe_url = payload.get("SubscribeURL")
        if not subscribe_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing SubscribeURL")
        confirmed = confirm_subscription(subscribe_url, settings.sns_signature_timeout_seconds)
        logger.info("SNS subscription confirmation=%s message_id=%s", confirmed, sns_message_id)
        return {"status": "confirmed" if confirmed else "failed"}
    if message_type == "UnsubscribeConfirmation":
        logger.info("SNS unsubscribe confirmation message_id=%s", sns_message_id)
        return {"status": "ok"}
    if message_type != "Notification":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported SNS message type")

    message_body = payload.get("Message")
    if not message_body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing SNS Message body")

    if isinstance(message_body, dict):
        message = message_body
    else:
        try:
            message = json.loads(message_body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid SNS Message JSON")

    mail = message.get("mail") or {}
    ses_message_id = mail.get("messageId")
    destinations = mail.get("destination") or []
    if isinstance(destinations, str):
        destinations = [destinations]
    notification_type = (message.get("notificationType") or "").lower()

    event_type = notification_type or "unknown"
    new_status = "unknown"
    smtp_response = None
    bounce_type = None
    complaint_type = None
    event_time = None

    bounced_recipients: list[str] = []
    complained_recipients: list[str] = []
    bounce_subtype = None
    complaint_user_agent = None
    processing_time_ms = None
    reporting_mta = None

    if notification_type == "bounce":
        bounce = message.get("bounce") or {}
        bounce_type = bounce.get("bounceType")
        bounce_subtype = bounce.get("bounceSubType")
        event_time = _parse_timestamp(bounce.get("timestamp"))
        bounced_recipients = [
            recipient.get("emailAddress")
            for recipient in bounce.get("bouncedRecipients") or []
            if recipient.get("emailAddress")
        ]
        new_status = "bounced"
    elif notification_type == "complaint":
        complaint = message.get("complaint") or {}
        complaint_type = complaint.get("complaintFeedbackType")
        complaint_user_agent = complaint.get("userAgent")
        event_time = _parse_timestamp(complaint.get("timestamp"))
        complained_recipients = [
            recipient.get("emailAddress")
            for recipient in complaint.get("complainedRecipients") or []
            if recipient.get("emailAddress")
        ]
        new_status = "complaint"
    elif notification_type == "delivery":
        delivery = message.get("delivery") or {}
        smtp_response = delivery.get("smtpResponse")
        processing_time_ms = delivery.get("processingTimeMillis")
        reporting_mta = delivery.get("reportingMTA")
        event_time = _parse_timestamp(delivery.get("timestamp"))
        new_status = "delivered"

    logs: list[models.EmailLog] = []
    if ses_message_id:
        query = db.query(models.EmailLog).filter(models.EmailLog.message_id == ses_message_id)
        if destinations:
            logs = query.filter(models.EmailLog.recipient_email.in_(destinations)).all()
        if not logs:
            logs = query.all()

    if logs:
        _update_logs(
            db,
            logs,
            status_value=new_status,
            event_type=event_type,
            event_time=event_time,
            smtp_response=smtp_response,
            bounce_type=bounce_type,
            bounce_subtype=bounce_subtype,
            complaint_type=complaint_type,
            ses_message_id=ses_message_id,
        )

        if notification_type in {"bounce", "complaint"}:
            reason = notification_type if notification_type else "event"
            should_suppress = notification_type == "complaint" or (
                notification_type == "bounce" and (bounce_type or "").lower() == "permanent"
            )
            if should_suppress:
                recipients = bounced_recipients or complained_recipients or destinations
                for log in logs:
                    for recipient_email in recipients or []:
                        _add_suppression(db, tenant_id=log.tenant_id, email=recipient_email, reason=reason)
    else:
        logger.warning("EmailLog not found for ses_message_id=%s", ses_message_id)

    if logs:
        for log in logs:
            _persist_event(
                db,
                email_log_id=log.id,
                ses_message_id=ses_message_id,
                sns_message_id=sns_message_id,
                event_type=event_type,
                topic_arn=topic_arn,
                signature_verified=signature_verified,
                payload=payload,
            )
    else:
        _persist_event(
            db,
            email_log_id=None,
            ses_message_id=ses_message_id,
            sns_message_id=sns_message_id,
            event_type=event_type,
            topic_arn=topic_arn,
            signature_verified=signature_verified,
            payload=payload,
        )

    db.commit()
    return {"status": new_status}
