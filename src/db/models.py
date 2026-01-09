"""Database models for the email delivery platform."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import declarative_base, relationship

from src.utils.datetime import utcnow
Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    contact_email = Column(String(320), nullable=False)
    ses_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    campaigns = relationship("Campaign", back_populates="tenant", cascade="all, delete-orphan")
    subscribers = relationship("Subscriber", back_populates="tenant", cascade="all, delete-orphan")
    suppressed_emails = relationship("SuppressedEmail", back_populates="tenant", cascade="all, delete-orphan")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(50), default="draft")
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="campaigns")
    email_logs = relationship("EmailLog", back_populates="campaign")


class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    email = Column(String(320), nullable=False, index=True)
    first_name = Column(String(120), nullable=True)
    last_name = Column(String(120), nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="subscribers")


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    subscriber_id = Column(Integer, ForeignKey("subscribers.id"), nullable=True)
    recipient_email = Column(String(320), nullable=True, index=True)
    message_id = Column(String(255), nullable=True, index=True)
    provider_job_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), default="queued")
    last_event_type = Column(String(50), nullable=True)
    last_event_at = Column(DateTime(timezone=True), nullable=True)
    last_smtp_response = Column(String(1024), nullable=True)
    bounce_type = Column(String(255), nullable=True)
    bounce_subtype = Column(String(255), nullable=True)
    complaint_type = Column(String(255), nullable=True)
    sent_at = Column(DateTime(timezone=True), default=utcnow)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    campaign = relationship("Campaign", back_populates="email_logs")
    events = relationship("EmailEvent", back_populates="email_log", cascade="all, delete-orphan")


class EmailEvent(Base):
    __tablename__ = "email_events"

    id = Column(Integer, primary_key=True)
    email_log_id = Column(Integer, ForeignKey("email_logs.id"), nullable=True, index=True)
    ses_message_id = Column(String(255), nullable=True, index=True)
    sns_message_id = Column(String(255), nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    topic_arn = Column(String(512), nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    payload_json = Column(Text, nullable=False)
    signature_verified = Column(Boolean, default=False)

    email_log = relationship("EmailLog", back_populates="events")


class SuppressedEmail(Base):
    __tablename__ = "suppressed_emails"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String(320), nullable=False, index=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="suppressed_emails")
