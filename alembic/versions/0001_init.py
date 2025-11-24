"""init

Revision ID: 0001_init
Revises: 
Create Date: 2025-01-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("contact_email", sa.String(length=320), nullable=False),
        sa.Column("ses_verified", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_tenants_id", "tenants", ["id"], unique=False)

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="draft"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_id", "campaigns", ["id"], unique=False)
    op.create_index("ix_campaigns_tenant_id", "campaigns", ["tenant_id"], unique=False)

    op.create_table(
        "subscribers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscribers_id", "subscribers", ["id"], unique=False)
    op.create_index("ix_subscribers_email", "subscribers", ["email"], unique=False)

    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("subscriber_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="queued"),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["subscriber_id"], ["subscribers.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_logs_id", "email_logs", ["id"], unique=False)


def downgrade():
    op.drop_index("ix_email_logs_id", table_name="email_logs")
    op.drop_table("email_logs")
    op.drop_index("ix_subscribers_email", table_name="subscribers")
    op.drop_index("ix_subscribers_id", table_name="subscribers")
    op.drop_table("subscribers")
    op.drop_index("ix_campaigns_tenant_id", table_name="campaigns")
    op.drop_index("ix_campaigns_id", table_name="campaigns")
    op.drop_table("campaigns")
    op.drop_index("ix_tenants_id", table_name="tenants")
    op.drop_table("tenants")
