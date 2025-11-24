"""Domain verification endpoints."""
from __future__ import annotations

import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.db import models
from src.db.session import get_db

router = APIRouter(prefix="/domains", tags=["domains"])


class DomainStatusResponse(BaseModel):
    tenant_id: int
    ses_verified: bool

    class Config:
        orm_mode = True


class DomainVerificationRequest(BaseModel):
    tenant_id: int
    domain: str

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("domain must be valid")
        return value


class DomainVerificationResponse(BaseModel):
    domain: str
    txt_name: str
    txt_value: str
    cname_name: str
    cname_value: str


class MarkVerifiedRequest(BaseModel):
    tenant_id: int


@router.get("/status", response_model=DomainStatusResponse)
def get_domain_status(tenant_id: int, db: Session = Depends(get_db)) -> DomainStatusResponse:
    """Return SES verification status for a tenant."""

    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return DomainStatusResponse(tenant_id=tenant.id, ses_verified=tenant.ses_verified)


@router.post("/request-verification", response_model=DomainVerificationResponse)
def request_domain_verification(payload: DomainVerificationRequest, db: Session = Depends(get_db)) -> DomainVerificationResponse:
    """Generate SES DNS records for domain verification."""

    tenant = db.query(models.Tenant).filter(models.Tenant.id == payload.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    token = secrets.token_hex(16)
    txt_name = f"_amazonses.{payload.domain}"
    txt_value = token
    cname_name = f"_amazonses.{payload.domain}"
    cname_value = f"{token}.amazonaws.com"

    return DomainVerificationResponse(
        domain=payload.domain,
        txt_name=txt_name,
        txt_value=txt_value,
        cname_name=cname_name,
        cname_value=cname_value,
    )


@router.patch("/mark-verified", response_model=DomainStatusResponse)
def mark_domain_verified(payload: MarkVerifiedRequest, db: Session = Depends(get_db)) -> DomainStatusResponse:
    """Mark a tenant's SES configuration as verified."""

    tenant = db.query(models.Tenant).filter(models.Tenant.id == payload.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    tenant.ses_verified = True
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return DomainStatusResponse(tenant_id=tenant.id, ses_verified=tenant.ses_verified)
