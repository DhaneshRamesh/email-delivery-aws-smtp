"""Email log query endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import models
from src.db.session import get_db

router = APIRouter(prefix="/email-logs", tags=["email-logs"])


class EmailLogResponse(BaseModel):
    id: int
    tenant_id: int
    campaign_id: int | None = None
    subscriber_id: int | None = None
    message_id: str
    status: str

    class Config:
        orm_mode = True


def _get_log(db: Session, log_id: int) -> models.EmailLog:
    log = db.query(models.EmailLog).filter(models.EmailLog.id == log_id).first()
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email log not found")
    return log


@router.get("/", response_model=list[EmailLogResponse])
def list_logs(tenant_id: int | None = Query(default=None), db: Session = Depends(get_db)) -> list[EmailLogResponse]:
    """List email logs optionally filtered by tenant."""

    query = db.query(models.EmailLog)
    if tenant_id is not None:
        query = query.filter(models.EmailLog.tenant_id == tenant_id)
    logs = query.order_by(models.EmailLog.created_at.desc()).all()
    return [EmailLogResponse.from_orm(log) for log in logs]


@router.get("/campaign/{campaign_id}", response_model=list[EmailLogResponse])
def list_campaign_logs(campaign_id: int, db: Session = Depends(get_db)) -> list[EmailLogResponse]:
    """List email logs for a campaign."""

    logs = (
        db.query(models.EmailLog)
        .filter(models.EmailLog.campaign_id == campaign_id)
        .order_by(models.EmailLog.created_at.desc())
        .all()
    )
    return [EmailLogResponse.from_orm(log) for log in logs]


@router.get("/{log_id}", response_model=EmailLogResponse)
def get_log(log_id: int, db: Session = Depends(get_db)) -> EmailLogResponse:
    """Get details of a single email log."""

    log = _get_log(db, log_id)
    return EmailLogResponse.from_orm(log)
