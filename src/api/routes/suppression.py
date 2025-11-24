"""Suppression list management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.db import models
from src.db.session import get_db

router = APIRouter(prefix="/suppression", tags=["suppression"])


class SuppressionCreate(BaseModel):
    tenant_id: int
    email: str
    reason: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("email must be valid")
        return value


class SuppressionResponse(BaseModel):
    id: int
    tenant_id: int
    email: str
    reason: str | None = None

    class Config:
        orm_mode = True


def _get_entry(db: Session, entry_id: int) -> models.SuppressedEmail:
    entry = db.query(models.SuppressedEmail).filter(models.SuppressedEmail.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression not found")
    return entry


@router.post("/", response_model=SuppressionResponse, status_code=status.HTTP_201_CREATED)
def add_suppression(payload: SuppressionCreate, db: Session = Depends(get_db)) -> SuppressionResponse:
    """Add an email to the suppression list."""

    existing = (
        db.query(models.SuppressedEmail)
        .filter(models.SuppressedEmail.tenant_id == payload.tenant_id, models.SuppressedEmail.email == payload.email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already suppressed")

    entry = models.SuppressedEmail(
        tenant_id=payload.tenant_id,
        email=payload.email,
        reason=payload.reason,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return SuppressionResponse.from_orm(entry)


@router.get("/", response_model=list[SuppressionResponse])
def list_suppression(tenant_id: int | None = Query(default=None), db: Session = Depends(get_db)) -> list[SuppressionResponse]:
    """List suppressed emails optionally filtered by tenant."""

    query = db.query(models.SuppressedEmail)
    if tenant_id is not None:
        query = query.filter(models.SuppressedEmail.tenant_id == tenant_id)
    entries = query.order_by(models.SuppressedEmail.created_at.desc()).all()
    return [SuppressionResponse.from_orm(entry) for entry in entries]


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def remove_suppression(entry_id: int, db: Session = Depends(get_db)) -> Response:
    """Remove an email from suppression list."""

    entry = _get_entry(db, entry_id)
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
