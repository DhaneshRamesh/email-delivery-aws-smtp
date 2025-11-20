"""Routes for sending transactional emails."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from src.core.config import settings
from src.core.rate_limit import create_rate_limiter
from src.queue.worker import enqueue_email_job
from src.services.ses import ses_service

router = APIRouter(prefix="/send", tags=["send"])
_rate_limiter = create_rate_limiter(settings.rate_limit_per_minute)


class SendTestRequest(BaseModel):
    recipient: str
    subject: str
    body: str
    enqueue: bool = False

    @field_validator("recipient")
    @classmethod
    def validate_recipient(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("recipient must be an email address")
        return value


class SendTestResponse(BaseModel):
    message_id: str
    queued: bool = False


@router.post("/send-test", response_model=SendTestResponse)
async def send_test_email(request: SendTestRequest) -> SendTestResponse:
    """Send a simple email via AWS SES."""

    await _rate_limiter.check("global-test")

    if request.enqueue:
        job = enqueue_email_job(
            subject=request.subject,
            recipient=request.recipient,
            body=request.body,
        )
        return SendTestResponse(message_id=job.id, queued=True)

    message_id = ses_service.send_email(
        subject=request.subject,
        recipient=request.recipient,
        text_body=request.body,
    )
    return SendTestResponse(message_id=message_id, queued=False)
