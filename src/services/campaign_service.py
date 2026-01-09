"""Helpers for campaign validation and bulk email enqueuing."""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from src.db import models
from src.queue.worker import enqueue_email_job
from src.utils.logger import logger


def validate_campaign(db: Session, campaign_id: int) -> models.Campaign:
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise ValueError("Campaign not found")
    return campaign


def load_recipients(db: Session, tenant_id: int) -> list[models.Subscriber]:
    suppressed = (
        db.query(models.SuppressedEmail.email)
        .filter(models.SuppressedEmail.tenant_id == tenant_id)
        .subquery()
    )
    recipients = (
        db.query(models.Subscriber)
        .filter(
            models.Subscriber.tenant_id == tenant_id,
            models.Subscriber.status == "active",
            ~models.Subscriber.email.in_(suppressed),
        )
        .all()
    )
    return recipients


def enqueue_bulk_emails(db: Session, campaign: models.Campaign, subscribers: Iterable[models.Subscriber]) -> int:
    enqueued = 0
    for subscriber in subscribers:
        email_log = models.EmailLog(
            tenant_id=campaign.tenant_id,
            campaign_id=campaign.id,
            subscriber_id=subscriber.id,
            status="queued",
            recipient_email=subscriber.email,
        )
        db.add(email_log)
        db.flush()
        job = enqueue_email_job(
            subject=campaign.subject,
            recipient=subscriber.email,
            body=campaign.body,
            email_log_id=email_log.id,
        )
        email_log.provider_job_id = job.id
        enqueued += 1
    logger.info("Campaign %s enqueued %s messages", campaign.id, enqueued)
    return enqueued


def update_campaign_status(db: Session, campaign_id: int, status: str) -> None:
    campaign = validate_campaign(db, campaign_id)
    campaign.status = status
    db.add(campaign)
