"""initial helm_mcp tables

Revision ID: 0001helm_mcp
Revises:
Create Date: 2026-05-02
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0001helm_mcp"
down_revision = None
branch_labels = ("helm-mcp",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "helm_mcp_call_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(256), nullable=False),
        sa.Column(
            "input_args",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_helm_mcp_call_logs_user_id",    "helm_mcp_call_logs", ["user_id"])
    op.create_index("ix_helm_mcp_call_logs_tool_name",  "helm_mcp_call_logs", ["tool_name"])
    op.create_index("ix_helm_mcp_call_logs_status",     "helm_mcp_call_logs", ["status"])
    op.create_index("ix_helm_mcp_call_logs_created_at", "helm_mcp_call_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("helm_mcp_call_logs")
