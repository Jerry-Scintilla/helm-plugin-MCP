from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MCPToolDefSchema(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    required_permission: str | None
    provider_plugin: str
    assigned_server_slug: str | None = None


class MCPCallLogSchema(BaseModel):
    id: int
    user_id: int
    tool_name: str
    input_args: dict[str, Any]
    status: str
    error_message: str | None
    duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Connection config ─────────────────────────────────────────────────────────

class ServerConfigEntry(BaseModel):
    slug: str
    name: str
    sse_url: str
    messages_url: str
    tool_count: int


class MCPConfigSchema(BaseModel):
    auth_param: str
    auth_prefix: str
    protocol_version: str
    servers: list[ServerConfigEntry]


class CreateAPIKeyRequest(BaseModel):
    name: str


# ── Server management ─────────────────────────────────────────────────────────

_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$"


class MCPServerSchema(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None
    max_tools: int
    is_enabled: bool
    sort_order: int
    tool_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateServerRequest(BaseModel):
    slug: str = Field(..., pattern=_SLUG_PATTERN, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    max_tools: int = Field(default=12, ge=1, le=64)
    sort_order: int = 0


class UpdateServerRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    max_tools: int | None = Field(default=None, ge=1, le=64)
    is_enabled: bool | None = None
    sort_order: int | None = None


# ── Assignments ───────────────────────────────────────────────────────────────

class AssignmentsResponse(BaseModel):
    assigned: dict[str, list[str]]  # slug -> [tool_name, ...]
    unassigned: list[str]


class MoveAssignmentRequest(BaseModel):
    tool_name: str
    target_server_id: int | None  # None → move to unassigned pool


class BulkAssignmentItem(BaseModel):
    tool_name: str
    server_id: int | None
    sort_order: int = 0


class BulkAssignmentRequest(BaseModel):
    assignments: list[BulkAssignmentItem]
