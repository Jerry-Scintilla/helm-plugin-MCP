from __future__ import annotations

from pathlib import Path

from app.plugins.base import HelmPlugin, PermissionDef, PluginContext, SidebarItem
from app.plugins.registry import extension_registry


class HelmMCPPlugin(HelmPlugin):
    name = "helm-mcp"
    version = "0.1.2"
    author = "Jerry_Scintilla"
    description = "通过 Model Context Protocol (MCP) 将 Helm 暴露给大型语言模型"
    helm_sdk_version = ">=1.0,<2.0"

    # ── Router ────────────────────────────────────────────────────────────────

    def get_router(self):
        from helm_mcp.routers import router
        return router

    # ── Permissions ───────────────────────────────────────────────────────────

    def get_permissions(self) -> list[PermissionDef]:
        return [
            PermissionDef("mcp.access", "global", "通过 MCP 协议访问 Helm 系统"),
            PermissionDef("mcp.admin",  "global", "管理 MCP 配置和查看所有会话日志"),
        ]

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def get_sidebar_items(self) -> list[SidebarItem]:
        return [SidebarItem("MCP 接入", "/plugins/helm-mcp", "🤖", order=200)]

    # ── Frontend ──────────────────────────────────────────────────────────────

    def get_static_dir(self):
        return Path(__file__).parent / "frontend" / "dist"

    def get_frontend_dev_url(self):
        return None  # set to "http://localhost:5174" during local development

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enable(self, ctx: PluginContext) -> None:
        """Register the built-in CoreToolProvider under the mcp.tool_provider point."""
        from helm_mcp.tool_providers.core import CoreToolProvider
        extension_registry.register("mcp.tool_provider", CoreToolProvider(), self.name)

    def on_disable(self, ctx: PluginContext) -> None:
        """Cancel all active SSE connections before the router is unmounted.

        Without this, _sse_transport's internal session channels have no reader
        after the /messages/ route is removed, causing handle_post_message() to
        block forever and exhaust the DB connection pool.
        """
        from helm_mcp.mcp_server import cancel_all_sse_connections
        cancel_all_sse_connections()
