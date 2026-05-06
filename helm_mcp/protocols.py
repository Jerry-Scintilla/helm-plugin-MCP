"""
Public protocol contract for the MCP tool provider extension point.

Other plugins import from this module:
    from helm_mcp.protocols import MCPToolDef, MCPToolProvider

This file must have no side-effects so it is safe to import
even when the helm-mcp plugin itself is not active.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.user import User


@dataclass
class MCPToolDef:
    """Describes a single MCP tool exposed by a provider plugin."""

    name: str
    description: str
    input_schema: dict
    required_permission: str | None = None


@runtime_checkable
class MCPToolProvider(Protocol):
    """
    Implement this Protocol and register with:
        extension_registry.register("mcp.tool_provider", self, self.name)
    in on_enable() to automatically expose your tools via MCP.

    Example (in another plugin's plugin.py):

        from helm_mcp.protocols import MCPToolDef, MCPToolProvider

        class MyPlugin(HelmPlugin, MCPToolProvider):
            def get_mcp_tools(self) -> list[MCPToolDef]:
                return [
                    MCPToolDef(
                        name="my_tool",
                        description="Does something useful",
                        input_schema={"type": "object", "properties": {}, "required": []},
                        required_permission="my-plugin.read",
                    )
                ]

            async def call_mcp_tool(self, name, args, user, db) -> dict:
                if name == "my_tool":
                    return {"result": "..."}
                raise ValueError(f"Unknown tool: {name}")

            def on_enable(self, ctx):
                extension_registry.register("mcp.tool_provider", self, self.name)
    """

    def get_mcp_tools(self) -> list[MCPToolDef]:
        """Return the list of tools this provider exposes."""
        ...

    async def call_mcp_tool(
        self,
        name: str,
        args: dict,
        user: "User",
        db: "AsyncSession",
    ) -> dict:
        """
        Execute the named tool and return a JSON-serialisable dict.

        Raise ValueError for unknown tool names.
        Raise PermissionError if the user lacks a required permission
        (the MCP server also checks permissions before calling this).
        """
        ...
