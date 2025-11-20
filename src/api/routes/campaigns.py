"""Campaign management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import models
from src.db.session import get_db

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    tenant_id: int
    name: str
    subject: str
    body: str


class CampaignResponse(BaseModel):
    id: int
    name: str
    subject: str
    status: str

    class Config:
        orm_mode = True


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
