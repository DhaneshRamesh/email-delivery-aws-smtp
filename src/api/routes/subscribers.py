"""Subscriber management endpoints."""
from __future__ import annotations

import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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


class SubscriberUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    status: str | None = None


class SubscriberResponse(BaseModel):
    id: int
    tenant_id: int
    email: str
    first_name: str | None = None
    last_name: str | None = None
    status: str

    class Config:
        orm_mode = True


class BulkImportRequest(BaseModel):
    tenant_id: int
    csv_text: str


class BulkImportResponse(BaseModel):
    imported: int
    skipped: int


def _get_subscriber(db: Session, subscriber_id: int) -> models.Subscriber:
    subscriber = db.query(models.Subscriber).filter(models.Subscriber.id == subscriber_id).first()
    if subscriber is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscriber not found")
    return subscriber


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


@router.get("/", response_model=list[SubscriberResponse])
def list_subscribers(
    tenant_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[SubscriberResponse]:
    """List subscribers, optionally filtered by tenant."""

    query = db.query(models.Subscriber)
    if tenant_id is not None:
        query = query.filter(models.Subscriber.tenant_id == tenant_id)
    subscribers = query.order_by(models.Subscriber.created_at.desc()).all()
    return [SubscriberResponse.from_orm(s) for s in subscribers]


@router.get("/{subscriber_id}", response_model=SubscriberResponse)
def get_subscriber(subscriber_id: int, db: Session = Depends(get_db)) -> SubscriberResponse:
    """Retrieve a subscriber by ID."""

    subscriber = _get_subscriber(db, subscriber_id)
    return SubscriberResponse.from_orm(subscriber)


@router.patch("/{subscriber_id}", response_model=SubscriberResponse)
def update_subscriber(
    subscriber_id: int,
    payload: SubscriberUpdate,
    db: Session = Depends(get_db),
) -> SubscriberResponse:
    """Update subscriber attributes."""

    subscriber = _get_subscriber(db, subscriber_id)
    if payload.first_name is not None:
        subscriber.first_name = payload.first_name
    if payload.last_name is not None:
        subscriber.last_name = payload.last_name
    if payload.status is not None:
        subscriber.status = payload.status

    db.add(subscriber)
    db.commit()
    db.refresh(subscriber)
    return SubscriberResponse.from_orm(subscriber)


@router.delete("/{subscriber_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_subscriber(subscriber_id: int, db: Session = Depends(get_db)) -> Response:
    """Remove a subscriber."""

    subscriber = _get_subscriber(db, subscriber_id)
    db.delete(subscriber)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bulk-import", response_model=BulkImportResponse)
def bulk_import_subscribers(payload: BulkImportRequest, db: Session = Depends(get_db)) -> BulkImportResponse:
    """Import subscribers from CSV text (columns: email, first_name, last_name)."""

    created = 0
    skipped = 0
    reader = csv.DictReader(io.StringIO(payload.csv_text.strip()))
    required_columns = {"email"}
    if not required_columns.issubset(set(reader.fieldnames or [])):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must include email column")

    for row in reader:
        email = (row.get("email") or "").strip()
        if not email or "@" not in email:
            skipped += 1
            continue
        exists = (
            db.query(models.Subscriber)
            .filter(models.Subscriber.tenant_id == payload.tenant_id, models.Subscriber.email == email)
            .first()
        )
        if exists:
            skipped += 1
            continue
        subscriber = models.Subscriber(
            tenant_id=payload.tenant_id,
            email=email,
            first_name=(row.get("first_name") or "").strip() or None,
            last_name=(row.get("last_name") or "").strip() or None,
        )
        db.add(subscriber)
        created += 1

    db.commit()
    return BulkImportResponse(imported=created, skipped=skipped)
