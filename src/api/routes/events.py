"""Inbound webhook handlers for SES/SNS notifications."""
from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.db import models
from src.db.session import get_db
from src.utils.logger import logger

router = APIRouter(prefix="/events", tags=["events"])


def _update_email_log(db: Session, message_id: str, new_status: str) -> None:
    log = db.query(models.EmailLog).filter(models.EmailLog.message_id == message_id).first()
    if log:
        log.status = new_status
        db.add(log)
        db.commit()
    else:
        logger.warning("EmailLog not found for message_id=%s", message_id)


@router.post("/sns")
async def handle_sns_notification(payload: dict, db: Session = Depends(get_db)) -> dict[str, str]:
    """Handle SES SNS notifications for bounces/complaints."""

    message_type = payload.get("Type")
    if message_type == "SubscriptionConfirmation":
        return {"status": "confirmed"}
    if message_type != "Notification":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported SNS message type")

    message_body = payload.get("Message")
    if not message_body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing SNS Message body")

    try:
        message = json.loads(message_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid SNS Message JSON")

    mail = message.get("mail") or {}
    message_id = mail.get("messageId")
    if not message_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing messageId")

    notification_type = (message.get("notificationType") or "").lower()
    if notification_type == "bounce":
        new_status = "bounced"
    elif notification_type == "complaint":
        new_status = "complaint"
    else:
        new_status = "delivered"

    _update_email_log(db, message_id, new_status)
    return {"status": new_status}
