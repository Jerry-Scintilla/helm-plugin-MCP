from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import get_current_user, require_permission
from app.models.user import User
from app.plugins.registry import extension_registry

from helm_mcp.mcp_server import (
    drop_bundle,
    get_bundle,
    handle_sse_connection,
)
from helm_mcp.models import MCPCallLog, MCPServer, MCPToolAssignment
from helm_mcp.protocols import MCPToolProvider
from helm_mcp.schemas import (
    AssignmentsResponse,
    BulkAssignmentRequest,
    CreateAPIKeyRequest,
    CreateServerRequest,
    MCPCallLogSchema,
    MCPConfigSchema,
    MCPServerSchema,
    MCPToolDefSchema,
    MoveAssignmentRequest,
    ServerConfigEntry,
    UpdateServerRequest,
)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# MCP transport endpoints (per-slug)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/sse/{slug}", include_in_schema=False)
async def sse_endpoint(
    request: Request,
    slug: str = Path(...),
    api_key: str = Query(..., description="hlm_ 前缀的 API 密钥"),
) -> Response:
    """MCP SSE entry point for a specific logical server."""
    async with _session() as db:
        server = await _get_server_by_slug(db, slug)
        if server is None or not server.is_enabled:
            raise HTTPException(status_code=404, detail=f"server not found: {slug}")
    await handle_sse_connection(slug, request, api_key)
    return Response()


@router.post("/messages/{slug}/", include_in_schema=False)
@router.post("/messages/{slug}/{path:path}", include_in_schema=False)
async def messages_endpoint(request: Request, slug: str = Path(...)) -> Response:
    """MCP client→server message relay for a specific logical server."""
    bundle = get_bundle(slug)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"no active session for: {slug}")
    await bundle.transport.handle_post_message(
        request.scope, request.receive, request._send  # type: ignore[attr-defined]
    )
    return Response(status_code=202)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool browser (JWT auth)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/tools", response_model=list[MCPToolDefSchema])
async def list_tools(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mcp.access")),
) -> list[MCPToolDefSchema]:
    """All tools from all providers, annotated with their current server assignment."""
    # tool_name -> slug
    assignment_map = await _load_assignment_slug_map(db)

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
                    assigned_server_slug=assignment_map.get(tool_def.name),
                )
            )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Call log viewer
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/logs")
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    tool_name: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
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


# ═══════════════════════════════════════════════════════════════════════════════
# Connection config — one entry per server
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/config", response_model=MCPConfigSchema)
async def get_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mcp.access")),
) -> MCPConfigSchema:
    base = str(request.base_url).rstrip("/")
    plugin_base = f"{base}/api/v1/plugins/helm-mcp"

    servers_with_counts = await _list_servers_with_counts(db, enabled_only=True)

    entries = [
        ServerConfigEntry(
            slug=s.slug,
            name=s.name,
            sse_url=f"{plugin_base}/sse/{s.slug}",
            messages_url=f"{plugin_base}/messages/{s.slug}/",
            tool_count=count,
        )
        for (s, count) in servers_with_counts
    ]

    return MCPConfigSchema(
        auth_param="api_key",
        auth_prefix="hlm_",
        protocol_version="2024-11-05",
        servers=entries,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# API key creation (JWT auth, frontend use)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/keys")
async def create_api_key(
    body: CreateAPIKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("mcp.access")),
) -> dict:
    from helm_mcp.tool_providers.core import CoreToolProvider

    provider = CoreToolProvider()
    return await provider._create_api_key({"name": body.name}, current_user, db)


# ═══════════════════════════════════════════════════════════════════════════════
# Server management (mcp.admin)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/servers", response_model=list[MCPServerSchema])
async def list_servers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mcp.admin")),
) -> list[MCPServerSchema]:
    rows = await _list_servers_with_counts(db)
    return [
        MCPServerSchema(
            id=s.id, slug=s.slug, name=s.name, description=s.description,
            max_tools=s.max_tools, is_enabled=s.is_enabled, sort_order=s.sort_order,
            created_at=s.created_at, tool_count=count,
        )
        for (s, count) in rows
    ]


@router.post("/servers", response_model=MCPServerSchema)
async def create_server(
    body: CreateServerRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mcp.admin")),
) -> MCPServerSchema:
    existing = await _get_server_by_slug(db, body.slug)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"slug already exists: {body.slug}")

    server = MCPServer(
        slug=body.slug,
        name=body.name,
        description=body.description,
        max_tools=body.max_tools,
        sort_order=body.sort_order,
        is_enabled=True,
        created_at=datetime.now(UTC),
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    return MCPServerSchema(
        id=server.id, slug=server.slug, name=server.name, description=server.description,
        max_tools=server.max_tools, is_enabled=server.is_enabled,
        sort_order=server.sort_order, created_at=server.created_at, tool_count=0,
    )


@router.patch("/servers/{server_id}", response_model=MCPServerSchema)
async def update_server(
    server_id: int,
    body: UpdateServerRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mcp.admin")),
) -> MCPServerSchema:
    server = await db.get(MCPServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")

    if body.name is not None:
        server.name = body.name
    if body.description is not None:
        server.description = body.description
    if body.max_tools is not None:
        # Check capacity isn't shrunk below current tool count
        current = await _count_tools_in_server(db, server_id)
        if body.max_tools < current:
            raise HTTPException(
                status_code=400,
                detail=f"cannot shrink max_tools below current tool count ({current})",
            )
        server.max_tools = body.max_tools
    was_enabled = server.is_enabled
    if body.is_enabled is not None:
        server.is_enabled = body.is_enabled
    if body.sort_order is not None:
        server.sort_order = body.sort_order

    await db.commit()
    await db.refresh(server)

    # If we just disabled the server, drop its bundle to terminate live sessions
    if was_enabled and not server.is_enabled:
        drop_bundle(server.slug)

    count = await _count_tools_in_server(db, server_id)
    return MCPServerSchema(
        id=server.id, slug=server.slug, name=server.name, description=server.description,
        max_tools=server.max_tools, is_enabled=server.is_enabled,
        sort_order=server.sort_order, created_at=server.created_at, tool_count=count,
    )


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mcp.admin")),
) -> dict:
    server = await db.get(MCPServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")

    slug = server.slug
    await db.delete(server)
    await db.commit()

    # Tool assignment rows are SET NULL by the FK; tools fall back to "unassigned".
    drop_bundle(slug)
    return {"deleted": True, "slug": slug}


# ═══════════════════════════════════════════════════════════════════════════════
# Tool assignment management (mcp.admin)
# ═══════════════════════════════════════════════════════════════════════════════

async def _build_assignments(db: AsyncSession) -> AssignmentsResponse:
    all_tool_names = {
        tool.name
        for provider in extension_registry.get_all("mcp.tool_provider")
        for tool in provider.get_mcp_tools()
    }
    result = await db.execute(
        select(MCPToolAssignment.tool_name, MCPServer.slug)
        .join(MCPServer, MCPServer.id == MCPToolAssignment.server_id, isouter=True)
        .order_by(MCPToolAssignment.sort_order.asc())
    )
    rows = result.fetchall()
    assigned: dict[str, list[str]] = {}
    for tool_name, slug in rows:
        if slug is None:
            continue
        assigned.setdefault(slug, []).append(tool_name)
    unassigned = sorted(all_tool_names - {
        t for tools in assigned.values() for t in tools
    })
    return AssignmentsResponse(assigned=assigned, unassigned=unassigned)


@router.get("/assignments", response_model=AssignmentsResponse)
async def get_assignments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mcp.admin")),
) -> AssignmentsResponse:
    return await _build_assignments(db)


@router.post("/assignments/move", response_model=AssignmentsResponse)
async def move_assignment(
    body: MoveAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mcp.admin")),
) -> AssignmentsResponse:
    await _validate_tool_name(body.tool_name)

    if body.target_server_id is not None:
        target = await db.get(MCPServer, body.target_server_id)
        if target is None:
            raise HTTPException(status_code=404, detail="target server not found")
        # Capacity check (excluding the tool itself if it's already there)
        current_count = await _count_tools_in_server(
            db, body.target_server_id, exclude_tool=body.tool_name
        )
        if current_count + 1 > target.max_tools:
            raise HTTPException(
                status_code=400,
                detail=f"server '{target.slug}' is full ({current_count}/{target.max_tools})",
            )

    # Affected slugs whose bundles need to be invalidated (so list_tools reflects change)
    affected_slugs = await _slugs_currently_holding(db, body.tool_name)

    await _upsert_assignment(db, body.tool_name, body.target_server_id)
    await db.commit()

    if body.target_server_id is not None:
        target_slug = (await db.get(MCPServer, body.target_server_id)).slug  # type: ignore
        affected_slugs.add(target_slug)
    for slug in affected_slugs:
        drop_bundle(slug)

    return await _build_assignments(db)


@router.post("/assignments/bulk", response_model=AssignmentsResponse)
async def bulk_assign(
    body: BulkAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mcp.admin")),
) -> AssignmentsResponse:
    # Validate every tool name & capacity before writing anything
    counts_by_server: dict[int, int] = {}
    for item in body.assignments:
        await _validate_tool_name(item.tool_name)
        if item.server_id is not None:
            counts_by_server[item.server_id] = counts_by_server.get(item.server_id, 0) + 1

    for server_id, requested in counts_by_server.items():
        server = await db.get(MCPServer, server_id)
        if server is None:
            raise HTTPException(status_code=404, detail=f"server not found: {server_id}")
        if requested > server.max_tools:
            raise HTTPException(
                status_code=400,
                detail=f"server '{server.slug}' would have {requested} tools (max {server.max_tools})",
            )

    # Find which slugs we need to invalidate — every slug touched by old or new mapping
    tool_names = [item.tool_name for item in body.assignments]
    old_slugs = await _slugs_currently_holding_any(db, tool_names)
    new_slug_ids = {item.server_id for item in body.assignments if item.server_id is not None}
    if new_slug_ids:
        new_slug_rows = await db.execute(
            select(MCPServer.slug).where(MCPServer.id.in_(new_slug_ids))
        )
        affected_slugs = old_slugs | {row[0] for row in new_slug_rows.fetchall()}
    else:
        affected_slugs = old_slugs

    # Apply: delete all existing rows for these tool_names, then re-insert
    await db.execute(
        delete(MCPToolAssignment).where(MCPToolAssignment.tool_name.in_(tool_names))
    )
    now = datetime.now(UTC)
    for item in body.assignments:
        db.add(MCPToolAssignment(
            tool_name=item.tool_name,
            server_id=item.server_id,
            sort_order=item.sort_order,
            assigned_at=now,
        ))
    await db.commit()

    for slug in affected_slugs:
        drop_bundle(slug)

    return await _build_assignments(db)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _session():
    """Lazy import so tests/migrations can patch the session factory."""
    from app.core.database import AsyncSessionLocal
    return AsyncSessionLocal()


async def _get_server_by_slug(db: AsyncSession, slug: str) -> MCPServer | None:
    result = await db.execute(select(MCPServer).where(MCPServer.slug == slug))
    return result.scalar_one_or_none()


async def _list_servers_with_counts(
    db: AsyncSession, enabled_only: bool = False
) -> list[tuple[MCPServer, int]]:
    stmt = (
        select(MCPServer, func.count(MCPToolAssignment.tool_name))
        .join(
            MCPToolAssignment,
            MCPToolAssignment.server_id == MCPServer.id,
            isouter=True,
        )
        .group_by(MCPServer.id)
        .order_by(MCPServer.sort_order.asc(), MCPServer.id.asc())
    )
    if enabled_only:
        stmt = stmt.where(MCPServer.is_enabled == True)
    result = await db.execute(stmt)
    return [(row[0], int(row[1])) for row in result.fetchall()]


async def _count_tools_in_server(
    db: AsyncSession, server_id: int, exclude_tool: str | None = None
) -> int:
    stmt = (
        select(func.count(MCPToolAssignment.tool_name))
        .where(MCPToolAssignment.server_id == server_id)
    )
    if exclude_tool is not None:
        stmt = stmt.where(MCPToolAssignment.tool_name != exclude_tool)
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def _load_assignment_slug_map(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(
        select(MCPToolAssignment.tool_name, MCPServer.slug)
        .join(MCPServer, MCPServer.id == MCPToolAssignment.server_id)
    )
    return {name: slug for (name, slug) in result.fetchall()}


async def _slugs_currently_holding(db: AsyncSession, tool_name: str) -> set[str]:
    result = await db.execute(
        select(MCPServer.slug)
        .join(MCPToolAssignment, MCPToolAssignment.server_id == MCPServer.id)
        .where(MCPToolAssignment.tool_name == tool_name)
    )
    return {row[0] for row in result.fetchall()}


async def _slugs_currently_holding_any(db: AsyncSession, tool_names: list[str]) -> set[str]:
    if not tool_names:
        return set()
    result = await db.execute(
        select(MCPServer.slug)
        .join(MCPToolAssignment, MCPToolAssignment.server_id == MCPServer.id)
        .where(MCPToolAssignment.tool_name.in_(tool_names))
    )
    return {row[0] for row in result.fetchall()}


async def _upsert_assignment(
    db: AsyncSession, tool_name: str, server_id: int | None
) -> None:
    existing = await db.get(MCPToolAssignment, tool_name)
    if existing is None:
        db.add(MCPToolAssignment(
            tool_name=tool_name,
            server_id=server_id,
            assigned_at=datetime.now(UTC),
        ))
    else:
        existing.server_id = server_id
        existing.assigned_at = datetime.now(UTC)


async def _validate_tool_name(tool_name: str) -> None:
    """Ensure the tool currently exists in some provider's catalog."""
    known = {
        t.name
        for provider in extension_registry.get_all("mcp.tool_provider")
        for t in provider.get_mcp_tools()
    }
    if tool_name not in known:
        raise HTTPException(status_code=400, detail=f"unknown tool: {tool_name}")


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
