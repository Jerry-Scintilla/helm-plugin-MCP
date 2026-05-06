"""
Core MCP server module.

Contains:
- Module-level Server + SseServerTransport singletons
- ContextVar-based per-session user/permission propagation
- list_tools and call_tool handlers
- Authentication logic (API key → User + permission frozenset)
- SSE connection entry point called by routers.py
"""
from __future__ import annotations

import hashlib
import json
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

import mcp.types as types
from fastapi import HTTPException, Request
from mcp.server.lowlevel import Server
from mcp.server.sse import SseServerTransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.api_token import APIToken
from app.models.rbac import Permission, RolePermission, UserRole
from app.models.user import User
from app.plugins.registry import extension_registry

from helm_mcp.models import MCPCallLog
from helm_mcp.protocols import MCPToolProvider

# ── Module-level singletons ──────────────────────────────────────────────────

# One Server instance for the entire process; ContextVars provide per-session isolation.
_server = Server("helm-mcp")

# The SSE transport. The path here is the relative URL the transport tells the client
# to POST messages to — it must match the /messages/ route in routers.py.
_sse_transport = SseServerTransport("/api/v1/plugins/helm-mcp/messages/")

# Per-session context vars — set once per SSE connection, read by tool handlers.
_mcp_user: ContextVar[User] = ContextVar("mcp_user")
_mcp_perms: ContextVar[frozenset[str]] = ContextVar("mcp_perms")


# ── Helper: superuser sentinel ───────────────────────────────────────────────

_SUPERUSER_SENTINEL = "__superuser__"


def _has_perm(perms: frozenset[str], perm_name: str) -> bool:
    return (
        _SUPERUSER_SENTINEL in perms
        or "global.superuser" in perms
        or perm_name in perms
    )


# ── Helper: collect providers ────────────────────────────────────────────────

def _get_providers() -> list[MCPToolProvider]:
    return extension_registry.get_all("mcp.tool_provider")


def _build_tool_index() -> dict[str, tuple[MCPToolProvider, Any]]:
    """Returns {tool_name: (provider, MCPToolDef)}."""
    index: dict[str, tuple[MCPToolProvider, Any]] = {}
    for provider in _get_providers():
        for tool_def in provider.get_mcp_tools():
            index[tool_def.name] = (provider, tool_def)
    return index


# ── Authentication ────────────────────────────────────────────────────────────

async def _authenticate(api_key: str) -> tuple[User, frozenset[str]]:
    """
    Validate a raw hlm_... API key, load the owning User, and build
    the user's permission frozenset. Raises HTTPException on failure.
    """
    token_hash = hashlib.sha256(api_key.encode()).hexdigest()

    async with AsyncSessionLocal() as db:
        # Fetch the token + user in one query
        result = await db.execute(
            select(User)
            .join(APIToken, APIToken.user_id == User.id)
            .where(
                APIToken.token_hash == token_hash,
                APIToken.is_active == True,
                User.is_active == True,
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=401, detail="无效的 API 密钥")

        # Check token expiry
        token_result = await db.execute(
            select(APIToken).where(APIToken.token_hash == token_hash)
        )
        token = token_result.scalar_one()
        if token.expires_at and token.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=401, detail="API 密钥已过期")

        # Update last_used_at
        token.last_used_at = datetime.now(UTC)
        await db.commit()

        # Build permission set
        if user.is_superuser:
            perms: frozenset[str] = frozenset([_SUPERUSER_SENTINEL])
        else:
            perm_result = await db.execute(
                select(Permission.name)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .join(UserRole, UserRole.role_id == RolePermission.role_id)
                .where(UserRole.user_id == user.id)
            )
            perms = frozenset(row[0] for row in perm_result.fetchall())

    if not _has_perm(perms, "mcp.access"):
        raise HTTPException(
            status_code=403,
            detail="该 API 密钥对应的用户没有 mcp.access 权限",
        )

    return user, perms


# ── Call logger ───────────────────────────────────────────────────────────────

async def _log_call(
    user_id: int,
    tool_name: str,
    input_args: dict,
    status: str,
    error_message: str | None,
    duration_ms: int | None,
) -> None:
    """Write an audit row. Uses its own session to avoid contaminating callers."""
    try:
        async with AsyncSessionLocal() as db:
            log = MCPCallLog(
                user_id=user_id,
                tool_name=tool_name,
                input_args=input_args,
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
                created_at=datetime.now(UTC),
            )
            db.add(log)
            await db.commit()
    except Exception:
        pass  # logging failures must never break tool calls


# ── MCP Server handlers ───────────────────────────────────────────────────────

@_server.list_tools()
async def _handle_list_tools() -> list[types.Tool]:
    """
    Returns only the tools whose required_permission the current user holds.
    Silently omitting admin tools prevents LLMs from learning about them.
    """
    perms = _mcp_perms.get()
    tools: list[types.Tool] = []

    for provider in _get_providers():
        for tool_def in provider.get_mcp_tools():
            if tool_def.required_permission is not None:
                if not _has_perm(perms, tool_def.required_permission):
                    continue
            tools.append(
                types.Tool(
                    name=tool_def.name,
                    description=tool_def.description,
                    inputSchema=tool_def.input_schema,
                )
            )
    return tools


@_server.call_tool()
async def _handle_call_tool(
    name: str, arguments: dict
) -> list[types.TextContent]:
    """
    Dispatches a tool call to the correct provider.
    Enforces permissions, creates a fresh DB session per call, and logs every
    invocation to MCPCallLog.
    """
    user = _mcp_user.get()
    perms = _mcp_perms.get()

    tool_index = _build_tool_index()
    entry = tool_index.get(name)

    if entry is None:
        await _log_call(user.id, name, arguments, "error", "tool not found", None)
        raise ValueError(f"Unknown MCP tool: {name}")

    provider, tool_def = entry

    # Permission enforcement (defence-in-depth; list_tools already filters)
    if tool_def.required_permission and not _has_perm(perms, tool_def.required_permission):
        await _log_call(
            user.id, name, arguments, "denied",
            f"missing permission: {tool_def.required_permission}", None,
        )
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "permission_denied",
                        "required_permission": tool_def.required_permission,
                    }
                ),
            )
        ]

    start_ms = int(time.monotonic() * 1000)
    try:
        async with AsyncSessionLocal() as db:
            result = await provider.call_mcp_tool(name, arguments, user, db)
        duration = int(time.monotonic() * 1000) - start_ms
        await _log_call(user.id, name, arguments, "success", None, duration)
        return [
            types.TextContent(type="text", text=json.dumps(result, default=str))
        ]
    except Exception as exc:
        duration = int(time.monotonic() * 1000) - start_ms
        await _log_call(user.id, name, arguments, "error", str(exc), duration)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": type(exc).__name__, "detail": str(exc)}
                ),
            )
        ]


# ── SSE connection entry point ────────────────────────────────────────────────

async def handle_sse_connection(request: Request, api_key: str) -> None:
    """
    Called by the FastAPI GET /sse route.

    1. Authenticates the API key and loads the user + permissions.
    2. Binds them to ContextVars for the lifetime of this SSE task.
    3. Runs the MCP server over the SSE streams until the client disconnects.

    Note: request._send is a Starlette internal used by MCP SDK's own examples
    for direct SSE integration. This is the documented integration pattern.
    """
    user, perms = await _authenticate(api_key)

    user_token = _mcp_user.set(user)
    perm_token = _mcp_perms.set(perms)
    try:
        async with _sse_transport.connect_sse(
            request.scope, request.receive, request._send  # type: ignore[attr-defined]
        ) as streams:
            await _server.run(
                streams[0],
                streams[1],
                _server.create_initialization_options(),
            )
    finally:
        _mcp_user.reset(user_token)
        _mcp_perms.reset(perm_token)


def get_sse_transport() -> SseServerTransport:
    return _sse_transport
