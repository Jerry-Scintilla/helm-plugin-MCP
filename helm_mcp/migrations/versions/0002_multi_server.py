"""multi-server tables: helm_mcp_servers + helm_mcp_tool_assignments

Revision ID: 0002helm_mcp
Revises: 0001helm_mcp
Create Date: 2026-05-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0002helm_mcp"
down_revision = "0001helm_mcp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "helm_mcp_servers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("max_tools", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_index(
        "ix_helm_mcp_servers_slug", "helm_mcp_servers", ["slug"], if_not_exists=True
    )

    op.create_table(
        "helm_mcp_tool_assignments",
        sa.Column("tool_name", sa.String(256), primary_key=True),
        sa.Column(
            "server_id",
            sa.Integer(),
            sa.ForeignKey("helm_mcp_servers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_index(
        "ix_helm_mcp_tool_assignments_server_id",
        "helm_mcp_tool_assignments",
        ["server_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("helm_mcp_tool_assignments")
    op.drop_table("helm_mcp_servers")
