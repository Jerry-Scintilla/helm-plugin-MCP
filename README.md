# helm-plugin-mcp

A Helm plugin that exposes the [Helm EVE Online Fleet Management System](https://github.com/jerrysmh/helm) via the **Model Context Protocol (MCP)**, enabling AI assistants like Claude Desktop, Cursor, and cline to interact with Helm's full capabilities — user queries, plugin management, tools provided by other plugins, and more.

> **Status**: Alpha. No releases yet. Contributions and forks are welcome.

---

## Project Overview

`helm-plugin-mcp` acts as a bridge between Helm's plugin architecture and MCP-compatible AI clients:

- **Integrated tools**: Built-in tools for user info, character listing, plugin management, and API key operations
- **Plugin extensibility**: Other Helm plugins can register MCP tools via the `MCPToolProvider` protocol — no changes to this plugin required
- **RBAC integration**: Every tool is gated by Helm's existing permission system; unauthorized tools are silently hidden from the LLM
- **Audit logging**: All tool calls are recorded with user, timestamp, status, and duration

---

## Features

| Feature | Description |
|---------|-------------|
| **MCP SSE Transport** | Standard SSE-based transport, compatible with all MCP clients |
| **Helm RBAC Integration** | Tool visibility and execution both enforced against Helm permissions |
| **Dedicated API Keys** | `hlm_`-prefixed keys per account, individually revocable |
| **Plugin Auto-Discovery** | Plugins implementing `MCPToolProvider` auto-register their tools |
| **Audit Log** | Full call history visible to administrators |
| **Management UI** | Three-tab sidebar: API Keys, Tool Browser, Call Logs |

---

## Quick Start

### 1. Install the plugin

```bash
# Install Python package
pip install -e /path/to/helm-plugin-mcp

# Install via Helm admin API (requires global.plugin_manage permission)
curl -X POST http://localhost:8000/api/v1/admin/plugins/install \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"package_name": "helm-plugin-mcp"}'
```

### 2. Grant permissions

Add `mcp.access` to the roles that need MCP access. `mcp.admin` is required for viewing all audit logs and using `helm_manage_plugin`.

### 3. Create an API Key

**Web UI**: Navigate to **🤖 MCP Access** in the sidebar → **🔑 API Keys** tab.

**API**:
```bash
curl -X POST http://localhost:8000/api/v1/plugins/helm-mcp/keys \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "claude-desktop"}'
```

Copy the returned `api_key` value — it will **only be shown once**.

### 4. Configure your AI client

**Claude Desktop** (`~/.claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "helm": {
      "url": "http://your-helm-host/api/v1/plugins/helm-mcp/sse?api_key=hlm_xxx",
      "transport": "sse"
    }
  }
}
```

**Cursor / cline** (project-level or global MCP config):
```json
{
  "mcpServers": {
    "helm": {
      "url": "http://your-helm-host/api/v1/plugins/helm-mcp/sse?api_key=hlm_xxx",
      "transport": "sse"
    }
  }
}
```

Restart your AI client. Helm's tools will now be available in your conversations.

---

## Built-in Tools

| Tool | Permission | Description |
|------|------------|-------------|
| `helm_whoami` | `mcp.access` | Returns current user's id, username, roles, and permissions |
| `helm_list_characters` | `mcp.access` | Lists all EVE Online characters bound to the current user |
| `helm_list_plugins` | `mcp.access` | Lists all installed plugins, with optional `enabled_only` filter |
| `helm_manage_plugin` | `mcp.admin` | Enables or disables a plugin (`action: "enable"` / `"disable"`) |
| `helm_list_my_api_keys` | `mcp.access` | Lists the current user's API keys (prefixes only, secrets hidden) |
| `helm_create_mcp_api_key` | `mcp.access` | Creates a new API key for the current user |

---

## Architecture

```
AI Client (Claude Desktop / Cursor / cline)
    │
    │  GET /api/v1/plugins/helm-mcp/sse?api_key=hlm_xxx   ← SSE long-lived connection
    │  POST /api/v1/plugins/helm-mcp/messages/            ← JSON-RPC messages
    ▼
FastAPI Router
    │  Validate API Key → Load User + frozenset of permissions
    │  Bind to ContextVar (per-connection isolation)
    ▼
MCP Server (mcp.server.lowlevel.Server)
    ├── list_tools()   → filter by user permissions
    └── call_tool()    → dispatch to plugin's call_mcp_tool(), write audit log
            │
            ▼
ExtensionRegistry["mcp.tool_provider"]
    ├── CoreToolProvider        ← helm-mcp built-in tools
    ├── OtherPlugin             ← third-party plugin tools
    └── ...                     ← any number of plugins
```

**Permission enforcement happens at two independent levels:**

1. **`list_tools`**: Tools requiring a permission the user lacks are **silently invisible** to the LLM
2. **`call_tool`**: Even if a client bypasses `list_tools`, permissions are re-checked and the call is rejected

---

## For Plugin Developers

Other Helm plugins can expose tools via MCP by implementing the `MCPToolProvider` protocol. See the full development guide:

- [Plugin Developer Guide](./docs/README_zh.md) (Chinese)
- Extension point: `ExtensionRegistry["mcp.tool_provider"]`

### Minimal Example

```python
from helm_mcp.protocols import MCPToolDef, MCPToolProvider
from app.plugins.registry import extension_registry

class MyPlugin(HelmPlugin, MCPToolProvider):

    def get_mcp_tools(self) -> list[MCPToolDef]:
        return [
            MCPToolDef(
                name="my_plugin_do_thing",
                description="Does something useful",
                input_schema={
                    "type": "object",
                    "properties": {"item_id": {"type": "integer"}},
                    "required": ["item_id"],
                },
                required_permission="my-plugin.use",
            ),
        ]

    async def call_mcp_tool(self, name: str, args: dict, user: User, db: AsyncSession) -> dict:
        if name == "my_plugin_do_thing":
            return {"result": "done"}
        raise ValueError(f"Unknown tool: {name}")

    def on_enable(self, ctx: PluginContext) -> None:
        extension_registry.register("mcp.tool_provider", self, self.name)
```

---

## API Reference

All endpoints are mounted under `/api/v1/plugins/helm-mcp/`:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/sse` | API Key (`?api_key=`) | MCP SSE connection endpoint |
| `POST` | `/messages/` | — | MCP message relay (managed internally by SSE transport) |
| `GET` | `/tools` | JWT Bearer | Lists all registered MCP tools (for UI tool browser) |
| `GET` | `/logs` | JWT Bearer | Query audit logs (admin sees all, users see only their own) |
| `GET` | `/config` | JWT Bearer | Returns AI client connection configuration JSON |
| `POST` | `/keys` | JWT Bearer | Creates an MCP API key for the current user |

---

## Security Notes

- **API keys are shown only once** — copy immediately after creation; if lost, delete and recreate
- **Principle of least privilege** — create separate keys for different use cases with different roles
- **HTTPS required in production** — API keys in URL parameters may appear in access logs
- **Audit logs** — administrators can review all tool invocations for anomalies

---

## Documentation

| Document | Language | Description |
|----------|----------|-------------|
| [README](./README.md) | English | Project overview |
| [README_zh](./docs/README_zh.md) | 中文 | 项目说明（原始文档） |
| [Plugin Developer Guide](./docs/README_zh.md) | 中文 | Full plugin development documentation |

---

## Contributing

This plugin is in alpha stage. Contributions, issues, and forks are all welcome. To get started:

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Submit a pull request

For questions or discussions, please open an issue on GitHub.