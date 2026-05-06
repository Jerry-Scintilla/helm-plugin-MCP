from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MCPToolDefSchema(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    required_permission: str | None
    provider_plugin: str


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


class MCPConfigSchema(BaseModel):
    sse_url: str
    messages_url: str
    auth_param: str
    auth_prefix: str
    protocol_version: str


class CreateAPIKeyRequest(BaseModel):
    name: str
