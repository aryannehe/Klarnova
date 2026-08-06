"""initial incidents table

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("alert_fingerprint", sa.String(64), nullable=True),
        sa.Column("alert_name", sa.String(255), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="alertmanager"),
        sa.Column("severity", sa.String(8), nullable=False),
        sa.Column("priority", sa.String(4), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DETECTED"),
        sa.Column("affected_resource", sa.String(512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_incidents_alert_fingerprint", "incidents", ["alert_fingerprint"], unique=True
    )
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_priority", "incidents", ["priority"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_affected_resource", "incidents", ["affected_resource"])


def downgrade() -> None:
    op.drop_index("ix_incidents_affected_resource", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_priority", table_name="incidents")
    op.drop_index("ix_incidents_severity", table_name="incidents")
    op.drop_index("ix_incidents_alert_fingerprint", table_name="incidents")
    op.drop_table("incidents")
