"""Built-in MCP tools provided by the helm-mcp plugin itself."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from helm_mcp.protocols import MCPToolDef

if TYPE_CHECKING:
    pass


class CoreToolProvider:
    """Provides core Helm system tools over MCP."""

    # ── Tool catalog ─────────────────────────────────────────────────────────

    def get_mcp_tools(self) -> list[MCPToolDef]:
        return [
            MCPToolDef(
                name="helm_whoami",
                description="返回当前已认证用户的身份信息、所属角色和拥有的权限列表。",
                input_schema={"type": "object", "properties": {}, "required": []},
                required_permission=None,
            ),
            MCPToolDef(
                name="helm_list_characters",
                description="列出当前用户绑定的所有 EVE Online 角色及其基本信息。",
                input_schema={"type": "object", "properties": {}, "required": []},
                required_permission=None,
            ),
            MCPToolDef(
                name="helm_list_plugins",
                description="列出所有已安装的 Helm 插件，包括版本、描述和启用状态。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "enabled_only": {
                            "type": "boolean",
                            "description": "仅返回已启用的插件，默认 false",
                        }
                    },
                    "required": [],
                },
                required_permission=None,
            ),
            MCPToolDef(
                name="helm_manage_plugin",
                description="启用或禁用指定 Helm 插件（需要 mcp.admin 权限）。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "plugin_name": {
                            "type": "string",
                            "description": "插件 slug，如 'fleet-action'",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["enable", "disable"],
                            "description": "执行的操作",
                        },
                    },
                    "required": ["plugin_name", "action"],
                },
                required_permission="mcp.admin",
            ),
            MCPToolDef(
                name="helm_list_my_api_keys",
                description="列出当前用户创建的所有 API 密钥（仅显示前缀，不暴露完整密钥）。",
                input_schema={"type": "object", "properties": {}, "required": []},
                required_permission=None,
            ),
            MCPToolDef(
                name="helm_create_mcp_api_key",
                description=(
                    "为当前用户创建一个新的 MCP API 密钥（hlm_ 前缀）。"
                    "完整密钥只在创建时返回一次，请立即保存。"
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "密钥备注名称，如 'claude-desktop'",
                        }
                    },
                    "required": ["name"],
                },
                required_permission=None,
            ),
        ]

    # ── Tool dispatcher ───────────────────────────────────────────────────────

    async def call_mcp_tool(
        self, name: str, args: dict, user: User, db: AsyncSession
    ) -> dict:
        dispatch = {
            "helm_whoami":             self._whoami,
            "helm_list_characters":    self._list_characters,
            "helm_list_plugins":       self._list_plugins,
            "helm_manage_plugin":      self._manage_plugin,
            "helm_list_my_api_keys":   self._list_api_keys,
            "helm_create_mcp_api_key": self._create_api_key,
        }
        handler = dispatch.get(name)
        if handler is None:
            raise ValueError(f"Unknown core tool: {name}")
        return await handler(args, user, db)

    # ── Individual tool implementations ──────────────────────────────────────

    async def _whoami(self, args: dict, user: User, db: AsyncSession) -> dict:
        from sqlalchemy import select
        from app.models.rbac import Permission, Role, RolePermission, UserRole

        roles_result = await db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
        roles = [row[0] for row in roles_result.fetchall()]

        perms_result = await db.execute(
            select(Permission.name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user.id)
        )
        permissions = sorted({row[0] for row in perms_result.fetchall()})

        return {
            "id": user.id,
            "username": user.username,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "roles": roles,
            "permissions": permissions,
        }

    async def _list_characters(self, args: dict, user: User, db: AsyncSession) -> dict:
        from app.models.character import Character

        result = await db.execute(
            select(Character).where(Character.user_id == user.id)
        )
        chars = result.scalars().all()
        return {
            "characters": [
                {
                    "character_id": c.character_id,
                    "character_name": c.character_name,
                    "is_active": c.is_active,
                }
                for c in chars
            ]
        }

    async def _list_plugins(self, args: dict, user: User, db: AsyncSession) -> dict:
        from app.models.plugin import Plugin

        result = await db.execute(select(Plugin).order_by(Plugin.name))
        plugins = result.scalars().all()

        enabled_only: bool = args.get("enabled_only", False)
        items = [
            {
                "name": p.name,
                "version": p.version,
                "author": p.author,
                "description": p.description,
                "is_enabled": p.is_enabled,
                "status": p.status,
            }
            for p in plugins
            if not enabled_only or p.is_enabled
        ]
        return {"plugins": items}

    async def _manage_plugin(self, args: dict, user: User, db: AsyncSession) -> dict:
        plugin_name: str = args["plugin_name"]
        action: str = args["action"]

        try:
            from app.plugins.manager import enable_plugin, disable_plugin
        except ImportError as exc:
            raise RuntimeError(f"Plugin manager not available: {exc}") from exc

        if action == "enable":
            await enable_plugin(plugin_name)
        elif action == "disable":
            await disable_plugin(plugin_name)
        else:
            raise ValueError(f"Unknown action: {action}")

        return {"plugin_name": plugin_name, "action": action, "success": True}

    async def _list_api_keys(self, args: dict, user: User, db: AsyncSession) -> dict:
        from app.models.api_token import APIToken

        result = await db.execute(
            select(APIToken)
            .where(APIToken.user_id == user.id)
            .order_by(APIToken.created_at.desc())
        )
        tokens = result.scalars().all()
        return {
            "api_keys": [
                {
                    "id": t.id,
                    "name": t.name,
                    "token_prefix": t.token_prefix,
                    "scopes": t.scopes,
                    "is_active": t.is_active,
                    "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                    "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tokens
            ]
        }

    async def _create_api_key(self, args: dict, user: User, db: AsyncSession) -> dict:
        from datetime import UTC, datetime
        from app.core.api_auth import generate_api_token
        from app.models.api_token import APIToken

        name: str = args.get("name", "mcp-key")
        full_token, token_prefix, token_hash = generate_api_token()

        token = APIToken(
            user_id=user.id,
            name=name,
            token_prefix=token_prefix,
            token_hash=token_hash,
            scopes="",
            is_active=True,
        )
        db.add(token)
        await db.commit()
        await db.refresh(token)

        return {
            "api_key": full_token,
            "token_prefix": token_prefix,
            "name": name,
            "id": token.id,
            "warning": "请立即保存此密钥，它将不再显示。",
        }
