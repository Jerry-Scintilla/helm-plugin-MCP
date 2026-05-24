"""
Core MCP server module — multi-server variant.

Each logical MCP server (a row in helm_mcp_servers) gets its own ServerBundle
containing a dedicated mcp.server.lowlevel.Server and SseServerTransport.
Bundles are created lazily on first SSE connection and cached.

A tool is visible to a bundle only when an MCPToolAssignment maps it to that
bundle's slug. Tools without an assignment row are not exposed to any SSE
endpoint (admins manage them via the management UI).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
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

from helm_mcp.models import MCPCallLog, MCPServer, MCPToolAssignment
from helm_mcp.protocols import MCPToolDef, MCPToolProvider

# ── URL constants ─────────────────────────────────────────────────────────────

_MESSAGES_PATH_PREFIX = "/api/v1/plugins/helm-mcp/messages"


# ── Per-session context vars (shared across all bundles) ─────────────────────

_mcp_user: ContextVar[User] = ContextVar("mcp_user")
_mcp_perms: ContextVar[frozenset[str]] = ContextVar("mcp_perms")


# ── ServerBundle ──────────────────────────────────────────────────────────────

@dataclass
class ServerBundle:
    slug: str
    server: Server
    transport: SseServerTransport
    active_tasks: set["asyncio.Task[None]"] = field(default_factory=set)


_bundles: dict[str, ServerBundle] = {}
_bundles_lock = asyncio.Lock()


# ── Helper: superuser sentinel ───────────────────────────────────────────────

_SUPERUSER_SENTINEL = "__superuser__"


def _has_perm(perms: frozenset[str], perm_name: str) -> bool:
    return (
        _SUPERUSER_SENTINEL in perms
        or "global.superuser" in perms
        or perm_name in perms
    )


# ── Helper: collect providers & build tool index ────────────────────────────

def _get_providers() -> list[MCPToolProvider]:
    return extension_registry.get_all("mcp.tool_provider")


def _build_global_tool_index() -> dict[str, tuple[MCPToolProvider, MCPToolDef]]:
    """All tools currently exposed by all registered providers, keyed by tool name."""
    index: dict[str, tuple[MCPToolProvider, MCPToolDef]] = {}
    for provider in _get_providers():
        for tool_def in provider.get_mcp_tools():
            index[tool_def.name] = (provider, tool_def)
    return index


async def _tools_assigned_to(slug: str) -> dict[str, tuple[MCPToolProvider, MCPToolDef]]:
    """Subset of the global tool index whose assignment row points to this slug."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MCPToolAssignment.tool_name)
            .join(MCPServer, MCPServer.id == MCPToolAssignment.server_id)
            .where(MCPServer.slug == slug)
            .order_by(MCPToolAssignment.sort_order.asc())
        )
        assigned_names = {row[0] for row in result.fetchall()}

    global_index = _build_global_tool_index()
    return {name: entry for name, entry in global_index.items() if name in assigned_names}


# ── Authentication ────────────────────────────────────────────────────────────

async def _authenticate(api_key: str) -> tuple[User, frozenset[str]]:
    """Validate API key, load User and permission set."""
    token_hash = hashlib.sha256(api_key.encode()).hexdigest()

    async with AsyncSessionLocal() as db:
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

        token_result = await db.execute(
            select(APIToken).where(APIToken.token_hash == token_hash)
        )
        token = token_result.scalar_one()
        if token.expires_at and token.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=401, detail="API 密钥已过期")

        token.last_used_at = datetime.now(UTC)
        await db.commit()

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
        pass


# ── Bundle factory + handler binding ─────────────────────────────────────────

def _make_list_tools(slug: str):
    async def handler() -> list[types.Tool]:
        perms = _mcp_perms.get()
        tools_for_slug = await _tools_assigned_to(slug)
        out: list[types.Tool] = []
        for _, tool_def in tools_for_slug.values():
            if tool_def.required_permission is not None:
                if not _has_perm(perms, tool_def.required_permission):
                    continue
            out.append(
                types.Tool(
                    name=tool_def.name,
                    description=tool_def.description,
                    inputSchema=tool_def.input_schema,
                )
            )
        return out
    return handler


def _make_call_tool(slug: str):
    async def handler(name: str, arguments: dict) -> list[types.TextContent]:
        user = _mcp_user.get()
        perms = _mcp_perms.get()

        # Re-verify assignment at call time — protects against admins re-assigning
        # a tool between this session's list_tools and call_tool.
        tools_for_slug = await _tools_assigned_to(slug)
        entry = tools_for_slug.get(name)
        if entry is None:
            await _log_call(user.id, name, arguments, "error",
                            f"tool not assigned to server '{slug}'", None)
            raise ValueError(f"Unknown MCP tool for server '{slug}': {name}")

        provider, tool_def = entry

        if tool_def.required_permission and not _has_perm(perms, tool_def.required_permission):
            await _log_call(
                user.id, name, arguments, "denied",
                f"missing permission: {tool_def.required_permission}", None,
            )
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "permission_denied",
                        "required_permission": tool_def.required_permission,
                    }),
                )
            ]

        start_ms = int(time.monotonic() * 1000)
        try:
            async with AsyncSessionLocal() as db:
                result = await provider.call_mcp_tool(name, arguments, user, db)
            duration = int(time.monotonic() * 1000) - start_ms
            await _log_call(user.id, name, arguments, "success", None, duration)
            return [types.TextContent(type="text", text=json.dumps(result, default=str))]
        except Exception as exc:
            duration = int(time.monotonic() * 1000) - start_ms
            await _log_call(user.id, name, arguments, "error", str(exc), duration)
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": type(exc).__name__, "detail": str(exc)}),
                )
            ]
    return handler


async def _create_bundle(slug: str) -> ServerBundle:
    server = Server(f"helm-mcp:{slug}")
    transport = SseServerTransport(f"{_MESSAGES_PATH_PREFIX}/{slug}/")

    # Bind handlers using the lowlevel Server's decorator API
    server.list_tools()(_make_list_tools(slug))
    server.call_tool()(_make_call_tool(slug))

    return ServerBundle(slug=slug, server=server, transport=transport)


async def get_or_create_bundle(slug: str) -> ServerBundle:
    bundle = _bundles.get(slug)
    if bundle is not None:
        return bundle
    async with _bundles_lock:
        bundle = _bundles.get(slug)
        if bundle is None:
            bundle = await _create_bundle(slug)
            _bundles[slug] = bundle
    return bundle


def get_bundle(slug: str) -> ServerBundle | None:
    return _bundles.get(slug)


# ── SSE connection entry points ───────────────────────────────────────────────

async def _run_sse_session(
    bundle: ServerBundle,
    request: Request,
    user: User,
    perms: frozenset[str],
) -> None:
    user_token = _mcp_user.set(user)
    perm_token = _mcp_perms.set(perms)
    task = asyncio.current_task()
    if task is not None:
        bundle.active_tasks.add(task)
    try:
        async with bundle.transport.connect_sse(
            request.scope, request.receive, request._send  # type: ignore[attr-defined]
        ) as streams:
            await bundle.server.run(
                streams[0],
                streams[1],
                bundle.server.create_initialization_options(),
            )
    finally:
        _mcp_user.reset(user_token)
        _mcp_perms.reset(perm_token)
        if task is not None:
            bundle.active_tasks.discard(task)


async def handle_sse_connection(slug: str, request: Request, api_key: str) -> None:
    """Entry point called by GET /sse/{slug}.

    Caller (the route) is responsible for verifying that the slug exists and
    is enabled in the DB.
    """
    user, perms = await _authenticate(api_key)
    bundle = await get_or_create_bundle(slug)

    SSE_SESSION_DEADLINE = 300.0
    try:
        await asyncio.wait_for(
            _run_sse_session(bundle, request, user, perms),
            timeout=SSE_SESSION_DEADLINE,
        )
    except asyncio.TimeoutError:
        pass


# ── Lifecycle: cancel and drop bundles ───────────────────────────────────────

def _cancel_bundle_tasks(bundle: ServerBundle) -> None:
    """Cancel all active SSE tasks of one bundle. Fire-and-forget grace wait."""
    if not bundle.active_tasks:
        return

    CANCEL_TIMEOUT = 5.0
    for task in list(bundle.active_tasks):
        task.cancel()

    async def _wait() -> None:
        done, pending = await asyncio.wait(
            bundle.active_tasks, timeout=CANCEL_TIMEOUT
        )
        for t in pending:
            t.cancel()
        bundle.active_tasks.clear()

    try:
        asyncio.get_running_loop().call_soon(
            lambda: asyncio.create_task(_wait())
        )
    except RuntimeError:
        # No running loop — nothing we can do; tasks are already cancelled.
        pass


def cancel_all_sse_connections() -> None:
    """Cancel SSE on every bundle. Called by plugin on_disable."""
    for bundle in list(_bundles.values()):
        _cancel_bundle_tasks(bundle)


def drop_bundle(slug: str) -> None:
    """Cancel and remove a bundle. Called when a server row is deleted/disabled."""
    bundle = _bundles.pop(slug, None)
    if bundle is not None:
        _cancel_bundle_tasks(bundle)
