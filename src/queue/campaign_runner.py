"""Utilities to dispatch campaign emails to the queue."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.db.session import session_scope
from src.queue.worker import _get_queue, enqueue_email_job
from src.services import campaign_service
from src.utils.logger import logger


def _get_campaign(db: Session, campaign_id: int):
    return campaign_service.validate_campaign(db, campaign_id)


def run_campaign(campaign_id: int) -> int:
    """Enqueue emails for all subscribers of a campaign's tenant synchronously."""

    with session_scope() as db:
        campaign = _get_campaign(db, campaign_id)
        campaign_service.update_campaign_status(db, campaign.id, "sending")
        subscribers = campaign_service.load_recipients(db, campaign.tenant_id)
        enqueued = campaign_service.enqueue_bulk_emails(db, campaign, subscribers)
        campaign_service.update_campaign_status(db, campaign.id, "completed")
        logger.info("Campaign %s enqueued %s emails", campaign.id, enqueued)
        return enqueued


def _run_campaign_job(campaign_id: int) -> int:
    """RQ-friendly job to process a campaign."""

    with session_scope() as db:
        campaign = _get_campaign(db, campaign_id)
        campaign_service.update_campaign_status(db, campaign.id, "sending")
        subscribers = campaign_service.load_recipients(db, campaign.tenant_id)
        enqueued = campaign_service.enqueue_bulk_emails(db, campaign, subscribers)
        campaign_service.update_campaign_status(db, campaign.id, "completed")
        logger.info("Campaign job %s enqueued %s emails", campaign.id, enqueued)
        return enqueued


def enqueue_campaign_run(campaign_id: int):
    """Queue a campaign run on the default RQ queue."""

    queue = _get_queue()
    job = queue.enqueue(_run_campaign_job, kwargs={"campaign_id": campaign_id})
    logger.info("Enqueued campaign %s with job id %s", campaign_id, job.id)
    return job
