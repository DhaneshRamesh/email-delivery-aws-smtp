"""Subscriber management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.db import models
from src.db.session import get_db

router = APIRouter(prefix="/subscribers", tags=["subscribers"])


class SubscriberCreate(BaseModel):
    tenant_id: int
    email: str
    first_name: str | None = None
    last_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("email must be valid")
        return value


class SubscriberResponse(BaseModel):
    id: int
    email: str
    status: str

    class Config:
        orm_mode = True


@router.post("/", response_model=SubscriberResponse)
def add_subscriber(payload: SubscriberCreate, db: Session = Depends(get_db)) -> SubscriberResponse:
    """Add a subscriber to a tenant list if not already present."""

    existing = (
        db.query(models.Subscriber)
        .filter(models.Subscriber.tenant_id == payload.tenant_id, models.Subscriber.email == payload.email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Subscriber already exists")

    subscriber = models.Subscriber(
        tenant_id=payload.tenant_id,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    db.add(subscriber)
    db.commit()
    db.refresh(subscriber)
    return SubscriberResponse.from_orm(subscriber)
