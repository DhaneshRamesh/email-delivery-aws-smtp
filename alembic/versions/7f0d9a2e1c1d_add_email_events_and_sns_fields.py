"""add email events and sns metadata

Revision ID: 7f0d9a2e1c1d
Revises: c30dd1f959ec
Create Date: 2025-12-16 06:50:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7f0d9a2e1c1d"
down_revision = "c30dd1f959ec"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("email_logs", sa.Column("recipient_email", sa.String(length=320), nullable=True))
    op.add_column("email_logs", sa.Column("provider_job_id", sa.String(length=255), nullable=True))
    op.add_column("email_logs", sa.Column("last_event_type", sa.String(length=50), nullable=True))
    op.add_column("email_logs", sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_logs", sa.Column("last_smtp_response", sa.String(length=1024), nullable=True))
    op.add_column("email_logs", sa.Column("bounce_type", sa.String(length=255), nullable=True))
    op.add_column("email_logs", sa.Column("bounce_subtype", sa.String(length=255), nullable=True))
    op.add_column("email_logs", sa.Column("complaint_type", sa.String(length=255), nullable=True))
    op.add_column(
        "email_logs",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
    )
    op.alter_column("email_logs", "tenant_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("email_logs", "message_id", existing_type=sa.String(length=255), nullable=True)
    op.create_index(op.f("ix_email_logs_message_id"), "email_logs", ["message_id"], unique=False)
    op.create_index(op.f("ix_email_logs_provider_job_id"), "email_logs", ["provider_job_id"], unique=False)
    op.create_index(op.f("ix_email_logs_recipient_email"), "email_logs", ["recipient_email"], unique=False)

    op.create_table(
        "email_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_log_id", sa.Integer(), nullable=True),
        sa.Column("ses_message_id", sa.String(length=255), nullable=True),
        sa.Column("sns_message_id", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("topic_arn", sa.String(length=512), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["email_log_id"], ["email_logs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_events_email_log_id"), "email_events", ["email_log_id"], unique=False)
    op.create_index(op.f("ix_email_events_ses_message_id"), "email_events", ["ses_message_id"], unique=False)
    op.create_index(op.f("ix_email_events_sns_message_id"), "email_events", ["sns_message_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_email_events_sns_message_id"), table_name="email_events")
    op.drop_index(op.f("ix_email_events_ses_message_id"), table_name="email_events")
    op.drop_index(op.f("ix_email_events_email_log_id"), table_name="email_events")
    op.drop_table("email_events")

    op.drop_index(op.f("ix_email_logs_recipient_email"), table_name="email_logs")
    op.drop_index(op.f("ix_email_logs_provider_job_id"), table_name="email_logs")
    op.drop_index(op.f("ix_email_logs_message_id"), table_name="email_logs")
    op.alter_column("email_logs", "message_id", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("email_logs", "tenant_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("email_logs", "updated_at")
    op.drop_column("email_logs", "complaint_type")
    op.drop_column("email_logs", "bounce_subtype")
    op.drop_column("email_logs", "bounce_type")
    op.drop_column("email_logs", "last_smtp_response")
    op.drop_column("email_logs", "last_event_at")
    op.drop_column("email_logs", "last_event_type")
    op.drop_column("email_logs", "provider_job_id")
    op.drop_column("email_logs", "recipient_email")
