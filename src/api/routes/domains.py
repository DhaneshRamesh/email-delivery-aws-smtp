"""Domain verification endpoints."""
from __future__ import annotations

import secrets
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/domains", tags=["domains"])


class DomainVerificationRequest(BaseModel):
    tenant_id: int
    domain: str


class DomainVerificationResponse(BaseModel):
    domain: str
    verification_token: str
    instructions: str


@router.post("/verify", response_model=DomainVerificationResponse)
def verify_domain(payload: DomainVerificationRequest) -> DomainVerificationResponse:
    """Return stub DNS challenge instructions for SES domain verification."""

    token = secrets.token_hex(16)
    instructions = (
        "Add a TXT record named _amazonses.{domain} with the value {token}. "
        "Once AWS validates the record, mark the domain as verified in the admin UI."
    ).format(domain=payload.domain, token=token)

    return DomainVerificationResponse(
        domain=payload.domain,
        verification_token=token,
        instructions=instructions,
    )
