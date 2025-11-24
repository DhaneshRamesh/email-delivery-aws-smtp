"""Admin utilities for manual triggers."""
from __future__ import annotations

from fastapi import APIRouter

from src.queue.campaign_runner import enqueue_campaign_run, run_campaign

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/run-campaign/{campaign_id}")
def run_campaign_now(campaign_id: int) -> dict[str, int]:
    """Manually execute a campaign synchronously."""

    enqueued = run_campaign(campaign_id)
    return {"enqueued": enqueued}


@router.post("/enqueue-campaign/{campaign_id}")
def enqueue_campaign(campaign_id: int) -> dict[str, str]:
    """Enqueue a campaign for background processing."""

    job = enqueue_campaign_run(campaign_id)
    return {"job_id": job.id}
