from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import get_current_user, require_permission
from app.models.user import User
from app.plugins.registry import extension_registry

from helm_mcp.mcp_server import get_sse_transport, handle_sse_connection
from helm_mcp.models import MCPCallLog
from helm_mcp.protocols import MCPToolProvider
from helm_mcp.schemas import (
    CreateAPIKeyRequest,
    MCPCallLogSchema,
    MCPConfigSchema,
    MCPToolDefSchema,
)

router = APIRouter()


# ── GET /sse  ── MCP SSE connection (API key auth) ───────────────────────────

@router.get("/sse", include_in_schema=False)
async def sse_endpoint(
    request: Request,
    api_key: str = Query(..., description="hlm_ 前缀的 API 密钥"),
) -> Response:
    """
    MCP SSE transport entry point.
    Clients connect with ?api_key=hlm_xxx.
    Does NOT use Helm JWT auth — authenticates via the raw API key directly.
    """
    await handle_sse_connection(request, api_key)
    return Response()


# ── POST /messages/  ── MCP client→server message relay ──────────────────────

@router.post("/messages/", include_in_schema=False)
@router.post("/messages/{path:path}", include_in_schema=False)
async def messages_endpoint(request: Request) -> Response:
    """
    MCP client-to-server JSON-RPC message relay.
    The SseServerTransport routes messages to the correct SSE session
    using the session_id query parameter it injected during handshake.
    """
    transport = get_sse_transport()
    await transport.handle_post_message(
        request.scope, request.receive, request._send  # type: ignore[attr-defined]
    )
    return Response(status_code=202)


# ── GET /tools  ── Tool browser (JWT auth) ────────────────────────────────────

@router.get("/tools", response_model=list[MCPToolDefSchema])
async def list_tools(
    _: User = Depends(require_permission("mcp.access")),
) -> list[MCPToolDefSchema]:
    """Returns all available MCP tools from all registered providers."""
    result: list[MCPToolDefSchema] = []
    for provider in extension_registry.get_all("mcp.tool_provider"):
        plugin_name = getattr(provider, "_helm_plugin_name", type(provider).__name__)
        for tool_def in provider.get_mcp_tools():
            result.append(
                MCPToolDefSchema(
                    name=tool_def.name,
                    description=tool_def.description,
                    input_schema=tool_def.input_schema,
                    required_permission=tool_def.required_permission,
                    provider_plugin=plugin_name,
                )
            )
    return result


# ── GET /logs  ── Call log viewer (JWT auth) ──────────────────────────────────

@router.get("/logs")
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    tool_name: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Admins (mcp.admin or superuser) see all logs.
    Regular users see only their own logs.
    """
    stmt = select(MCPCallLog).order_by(desc(MCPCallLog.created_at))

    if not await _is_admin(current_user, db):
        stmt = stmt.where(MCPCallLog.user_id == current_user.id)

    if tool_name:
        stmt = stmt.where(MCPCallLog.tool_name == tool_name)
    if status:
        stmt = stmt.where(MCPCallLog.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    paged = stmt.offset((page - 1) * page_size).limit(page_size)
    logs = (await db.execute(paged)).scalars().all()

    return {
        "items": [MCPCallLogSchema.model_validate(log) for log in logs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── GET /config  ── Connection config for AI clients ─────────────────────────

@router.get("/config", response_model=MCPConfigSchema)
async def get_config(
    request: Request,
    _: User = Depends(require_permission("mcp.access")),
) -> MCPConfigSchema:
    """Returns the MCP connection config needed to set up Claude Desktop etc."""
    base = str(request.base_url).rstrip("/")
    plugin_base = f"{base}/api/v1/plugins/helm-mcp"
    return MCPConfigSchema(
        sse_url=f"{plugin_base}/sse",
        messages_url=f"{plugin_base}/messages/",
        auth_param="api_key",
        auth_prefix="hlm_",
        protocol_version="2024-11-05",
    )


# ── POST /keys  ── Create API key (JWT auth, for frontend use) ────────────────

@router.post("/keys")
async def create_api_key(
    body: CreateAPIKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("mcp.access")),
) -> dict:
    """Creates a new API key for the current user. Full token returned once only."""
    from helm_mcp.tool_providers.core import CoreToolProvider

    provider = CoreToolProvider()
    return await provider._create_api_key({"name": body.name}, current_user, db)


# ── Helper ────────────────────────────────────────────────────────────────────

async def _is_admin(user: User, db: AsyncSession) -> bool:
    if user.is_superuser:
        return True
    from app.models.rbac import Permission, RolePermission, UserRole

    result = await db.execute(
        select(Permission.name)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user.id, Permission.name == "mcp.admin")
    )
    return result.scalar_one_or_none() is not None
