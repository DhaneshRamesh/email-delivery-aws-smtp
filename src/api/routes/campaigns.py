"""Campaign management endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import models
from src.db.session import get_db
from src.queue.campaign_runner import enqueue_campaign_run, run_campaign

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    tenant_id: int
    name: str
    subject: str
    body: str


class CampaignUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body: str | None = None
    status: str | None = None


class CampaignResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    subject: str
    body: str
    status: str

    class Config:
        orm_mode = True


class CampaignSchedule(BaseModel):
    scheduled_at: datetime


class CampaignPreview(BaseModel):
    subject: str
    body: str


class CampaignSendResponse(BaseModel):
    enqueued: int
    status: str


@router.post("/", response_model=CampaignResponse)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)) -> CampaignResponse:
    """Create a campaign draft for a tenant."""

    campaign = models.Campaign(
        tenant_id=payload.tenant_id,
        name=payload.name,
        subject=payload.subject,
        body=payload.body,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return CampaignResponse.from_orm(campaign)


@router.get("/", response_model=list[CampaignResponse])
def list_campaigns(
    tenant_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CampaignResponse]:
    """List campaigns, optionally filtered by tenant."""

    query = db.query(models.Campaign)
    if tenant_id is not None:
        query = query.filter(models.Campaign.tenant_id == tenant_id)
    campaigns = query.order_by(models.Campaign.created_at.desc()).all()
    return [CampaignResponse.from_orm(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)) -> CampaignResponse:
    """Fetch a single campaign."""

    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return CampaignResponse.from_orm(campaign)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    db: Session = Depends(get_db),
) -> CampaignResponse:
    """Update campaign fields."""

    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    if payload.name is not None:
        campaign.name = payload.name
    if payload.subject is not None:
        campaign.subject = payload.subject
    if payload.body is not None:
        campaign.body = payload.body
    if payload.status is not None:
        campaign.status = payload.status

    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return CampaignResponse.from_orm(campaign)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a campaign."""

    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{campaign_id}/send-now", response_model=CampaignSendResponse)
def send_campaign_now(campaign_id: int) -> CampaignSendResponse:
    """Execute a campaign immediately."""

    enqueued = run_campaign(campaign_id)
    return CampaignSendResponse(enqueued=enqueued, status="completed")


@router.post("/{campaign_id}/schedule", response_model=CampaignResponse)
def schedule_campaign(campaign_id: int, payload: CampaignSchedule, db: Session = Depends(get_db)) -> CampaignResponse:
    """Set a scheduled send time for a campaign."""

    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    campaign.scheduled_at = payload.scheduled_at
    campaign.status = "scheduled"
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return CampaignResponse.from_orm(campaign)


@router.post("/{campaign_id}/cancel-schedule", response_model=CampaignResponse)
def cancel_campaign_schedule(campaign_id: int, db: Session = Depends(get_db)) -> CampaignResponse:
    """Cancel a scheduled campaign."""

    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    campaign.scheduled_at = None
    campaign.status = "draft"
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return CampaignResponse.from_orm(campaign)


@router.get("/{campaign_id}/preview", response_model=CampaignPreview)
def preview_campaign(campaign_id: int, db: Session = Depends(get_db)) -> CampaignPreview:
    """Return a preview of the campaign content."""

    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return CampaignPreview(subject=campaign.subject, body=campaign.body)

