"""Tenant management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.db import models
from src.db.session import get_db

router = APIRouter(prefix="/tenants", tags=["tenants"])


class TenantCreate(BaseModel):
    name: str
    contact_email: EmailStr


class TenantUpdate(BaseModel):
    name: str | None = None
    contact_email: EmailStr | None = None


class TenantResponse(BaseModel):
    id: int
    name: str
    contact_email: EmailStr
    ses_verified: bool

    class Config:
        orm_mode = True


def _get_tenant(db: Session, tenant_id: int) -> models.Tenant:
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)) -> TenantResponse:
    """Create a tenant."""

    tenant = models.Tenant(name=payload.name, contact_email=payload.contact_email)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return TenantResponse.from_orm(tenant)


@router.get("/", response_model=list[TenantResponse])
def list_tenants(db: Session = Depends(get_db)) -> list[TenantResponse]:
    """List all tenants."""

    tenants = db.query(models.Tenant).order_by(models.Tenant.created_at.desc()).all()
    return [TenantResponse.from_orm(t) for t in tenants]


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: int, db: Session = Depends(get_db)) -> TenantResponse:
    """Fetch a single tenant."""

    tenant = _get_tenant(db, tenant_id)
    return TenantResponse.from_orm(tenant)


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db)) -> TenantResponse:
    """Update tenant attributes."""

    tenant = _get_tenant(db, tenant_id)
    if payload.name is not None:
        tenant.name = payload.name
    if payload.contact_email is not None:
        tenant.contact_email = payload.contact_email
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return TenantResponse.from_orm(tenant)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_tenant(tenant_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a tenant."""

    tenant = _get_tenant(db, tenant_id)
    db.delete(tenant)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
