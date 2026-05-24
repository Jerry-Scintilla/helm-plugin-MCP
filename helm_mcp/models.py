from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MCPCallLog(Base):
    """Records every MCP tool call for auditing and the frontend log viewer."""

    __tablename__ = "helm_mcp_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    input_args: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # "success" | "error" | "denied"
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )


class MCPServer(Base):
    """A logical MCP server — a named grouping of tools (≤ max_tools) exposed
    at /sse/{slug}. Each one becomes a separate connection in the LLM client."""

    __tablename__ = "helm_mcp_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_tools: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class MCPToolAssignment(Base):
    """Maps a tool_name to the server that exposes it. Unique on tool_name
    enforces one-tool-one-server. server_id is nullable so that deleting a
    server returns its tools to the 'unassigned' pool rather than dropping rows."""

    __tablename__ = "helm_mcp_tool_assignments"

    tool_name: Mapped[str] = mapped_column(String(256), primary_key=True)
    server_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("helm_mcp_servers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
