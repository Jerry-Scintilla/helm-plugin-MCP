# helm-plugin-mcp

Expose the Helm EVE Online fleet management system completely to large language models through **Model Context Protocol (MCP)**. After installing this plugin, AI tools that support MCP protocol such as Claude Desktop, Cursor, and cline can directly operate all Helm functions——query characters, manage plugins, call tools provided by other plugins——just like a real operator with access credentials.

Starting from `v0.2.0`, tools can be split into **multiple small MCP servers** (up to 12 tools each), allowing each LLM connection to see only a subset of tools relevant to the current task——for example, fleet, intel, admin.

> **Status**: Alpha stage (current `0.2.0`), releases not yet available. Developers are welcome to contribute or fork for custom extensions.

---

## Project Overview

`helm-plugin-mcp` is a bridge between the Helm plugin system and MCP-compatible AI clients:

- **Built-in tools**: Provides user information queries, character lists, plugin management, API Key management, and more
- **Plugin extensibility**: Other Helm plugins can automatically register MCP tools by implementing the `MCPToolProvider` protocol, without modifying any code in this plugin
- **RBAC integration**: All tools are protected by Helm's existing permission system, so LLMs cannot see tools the user doesn't have access to
- **Audit logging**: Complete record of every tool invocation including user, timestamp, status, and duration

---

## Feature Overview

| Feature | Description |
|---------|-------------|
| **MCP SSE Transport** | Standard SSE protocol, compatible with all MCP clients |
| **Multiple Server Groups** | Tools split into multiple logical MCP servers (≤12 tools each); each group is an independent `/sse/{slug}` endpoint that LLM clients can subscribe to as needed |
| **Helm RBAC Integration** | Tool visibility and execution are controlled by Helm permissions |
| **Independent API Keys** | Each account can create multiple `hlm_` prefixed API Keys, independent of each other, revocable at any time; the same Key can connect to all server groups |
| **Automatic Plugin Discovery** | Plugins implementing `MCPToolProvider` automatically register tools; new tools enter an "unassigned" pool by default and are exposed only after admins assign them to a server group |
| **Audit Logging** | Admins can view call history for all users |
| **Management Interface** | Four-tab sidebar: API Keys, Server Groups, Tool Browser, Call Logs |

---

## Quick Start

### Step 1: Install Plugin

```bash
# Install Python package (editable mode for development)
pip install -e /path/to/helm-plugin-mcp

# Install via Helm management API (requires global.plugin_manage permission)
curl -X POST http://localhost:8000/api/v1/admin/plugins/install \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"package_name": "helm-plugin-mcp"}'
```

### Step 2: Assign Permissions

In the Helm management interface (or via API), add the `mcp.access` permission to the roles of users who need to use MCP. The `mcp.admin` permission is for viewing all audit logs and using `helm_manage_plugin`.

### Step 3: Create API Key

**Web UI**: Visit the sidebar **🤖 MCP Access** → **🔑 API Keys** tab.

**API**:
```bash
curl -X POST http://localhost:8000/api/v1/plugins/helm-mcp/keys \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "claude-desktop"}'
```

The `api_key` field in the response (`hlm_xxx...`) **appears only once**. Copy and save it immediately.

### Step 4: Create Server Groups and Assign Tools

Open **🤖 MCP Access** → **🗂 Server Groups** tab in Helm UI (requires `mcp.admin`):

1. Create one or more server groups (e.g., `fleet`, `intel`, `admin`), with a maximum of **12 tools** per group.
2. In the "Unassigned Pool" at the bottom of the page, find tools and move them to a group using the "Move to" dropdown menu.
3. Tools remaining in the unassigned pool **will not be exposed to any MCP client**——this is intentional to prevent unapproved tools from going live.

It's recommended to group tools by domain (business module), allowing each LLM connection to see only tools relevant to the current task.

### Step 5: Configure AI Client

The **🔑 API Keys** tab generates an independent JSON configuration for each enabled server group, which can be copied and pasted directly. Each group is an independent MCP connection.

**Claude Desktop** (`~/.claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "helm-fleet": {
      "url": "http://your-helm-host/api/v1/plugins/helm-mcp/sse/fleet?api_key=hlm_xxx",
      "transport": "sse"
    },
    "helm-intel": {
      "url": "http://your-helm-host/api/v1/plugins/helm-mcp/sse/intel?api_key=hlm_xxx",
      "transport": "sse"
    }
  }
}
```

The same `api_key` can connect to all groups——RBAC is still controlled by each tool's own `required_permission`.

Restart the AI client and you can use Helm features by group.

---

## Built-in Tools

The following tools are provided by `CoreToolProvider` and are immediately available after plugin installation:

| Tool Name | Required Permission | Description |
|-----------|-------------------|-------------|
| `helm_whoami` | `mcp.access` | Returns the current user's id, username, role list, and permission list |
| `helm_list_characters` | `mcp.access` | Lists all EVE Online characters bound to the current user |
| `helm_list_plugins` | `mcp.access` | Lists all installed plugins, supports `enabled_only` filter |
| `helm_manage_plugin` | `mcp.admin` | Enable or disable a specified plugin (`action: "enable"` or `"disable"`) |
| `helm_list_my_api_keys` | `mcp.access` | Lists the current user's API Keys (only shows prefix, not the full key) |
| `helm_create_mcp_api_key` | `mcp.access` | Creates a new API Key for the current user, full key returned only once |

---

## How It Works

```
AI Client (Claude Desktop / Cursor / cline)
    │  One independent connection per server group
    │  GET /api/v1/plugins/helm-mcp/sse/{slug}?api_key=hlm_xxx   ← SSE long connection
    │  POST /api/v1/plugins/helm-mcp/messages/{slug}/            ← JSON-RPC messages
    ▼
FastAPI Router Layer
    │  Validate API Key → Load User + permission frozenset
    │  Bind to ContextVar (current SSE connection isolated)
    │  Parse {slug} → ServerBundle (lazy create, dict cached)
    ▼
ServerBundle (one per slug)
    ├── mcp.server.lowlevel.Server("helm-mcp:{slug}")
    └── SseServerTransport("/api/v1/plugins/helm-mcp/messages/{slug}/")
        ├── list_tools()  → Query DB for tools assigned to this slug, filter by permissions
        └── call_tool()   → Re-verify slug assignment before dispatch to provider, write audit log
            │
            ▼
ExtensionRegistry["mcp.tool_provider"]
    ├── CoreToolProvider        ← helm-mcp built-in tools
    └── ...                     ← Any number of third-party plugins
```

**Key Design: Permissions/visibility enforced at three levels independently**

1. **Group Assignment**: Both `list_tools` and `call_tool` only consider tools where `MCPToolAssignment` points to the current bundle slug. Unassigned tools are invisible to all clients.
2. **`list_tools` Phase**: Tools lacking `required_permission` are **silently invisible** to the user——the LLM won't know admin tools exist.
3. **`call_tool` Phase**: Even if the client bypasses `list_tools` and calls directly, permissions are re-checked and denied. Additionally, tool slug assignment is re-verified, so admin group adjustments take effect immediately on active connections.

**Bundle Lifecycle**: Bundle is created and cached on first connection; assigning tools, disabling groups, or deleting groups all trigger `drop_bundle(slug)`, which cancels all active SSE sessions for that slug. Clients automatically reconnect and see the latest tool list.

---

## Adding MCP Tools to Other Plugins

Any Helm plugin can expose its functionality as MCP tools in just three steps, **without modifying any code in helm-mcp**.

For detailed development guide, see: [Plugin Development Guide](./Plugin_Dev_Guide/README.md)

### Quick Start (Three Steps)

**Step 1:** Import the protocol at the top of your plugin's `plugin.py`

```python
from helm_mcp.protocols import MCPToolDef, MCPToolProvider
from app.plugins.registry import extension_registry
```

**Step 2:** Have your plugin class implement the `MCPToolProvider` protocol

```python
class MyPlugin(HelmPlugin, MCPToolProvider):

    def get_mcp_tools(self) -> list[MCPToolDef]:
        """Declare the list of tools provided by this plugin."""
        return [
            MCPToolDef(
                name="my_tool_name",
                description="Explain to the LLM what this tool does",
                input_schema={
                    "type": "object",
                    "properties": {
                        "param_a": {"type": "string", "description": "Parameter description"},
                    },
                    "required": ["param_a"],
                },
                required_permission="my-plugin.read",  # None means only mcp.access required
            ),
        ]

    async def call_mcp_tool(
        self,
        name: str,
        args: dict,
        user: User,
        db: AsyncSession,
    ) -> dict:
        """Execute tool call, return JSON-serializable dict."""
        if name == "my_tool_name":
            param_a = args["param_a"]
            # ... business logic ...
            return {"result": "..."}
        raise ValueError(f"Unknown tool: {name}")
```

**Step 3:** Register in the `on_enable` hook

```python
    def on_enable(self, ctx: PluginContext) -> None:
        extension_registry.register("mcp.tool_provider", self, self.name)
        # ... other registration logic ...
```

Done. Your tools will automatically appear the next time the AI client refreshes the tool list.

### MCPToolDef Parameter Reference

```python
@dataclass
class MCPToolDef:
    name: str                        # Unique identifier for the tool, recommend plugin-name_action format
    description: str                 # Tool description shown to LLM, be as clear as possible
    input_schema: dict               # Standard JSON Schema (type=object), describes parameter structure
    required_permission: str | None  # Helm permission name; None means only mcp.access required
```

**`name` Naming Convention:** Use plugin name prefix to avoid conflicts with other plugins, e.g., `fleet_action_list_fleets`, `srp_submit_claim`.

**`input_schema` Format:** Must be a valid JSON Schema `object` type, `properties` and `required` can both be empty:

```python
# Tool with no parameters
input_schema = {"type": "object", "properties": {}, "required": []}

# Tool with parameters
input_schema = {
    "type": "object",
    "properties": {
        "fleet_id":  {"type": "integer", "description": "Fleet ID"},
        "include_alts": {"type": "boolean", "description": "Include alts, default false"},
    },
    "required": ["fleet_id"],
}
```

**`required_permission`:** Pass the permission names defined by your plugin (those declared in `get_permissions()`). Users lacking this permission won't see the tool during `list_tools`.

---

## Permission Reference

This plugin adds two global permissions, automatically written to the database on installation:

| Permission | Description |
|------------|-------------|
| `mcp.access` | Allows connecting via MCP protocol and calling tools. **Users must have this permission to use any MCP functionality.** |
| `mcp.admin` | Can view call logs for all users (regular users can only see their own), and call the `helm_manage_plugin` tool. |

> Users with `global.superuser` or `is_superuser=True` automatically have all permissions, including the above two.

---

## API Endpoint Reference

All endpoints are mounted under `/api/v1/plugins/helm-mcp/`:

### MCP Transport (by Server Group)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/sse/{slug}` | API Key (`?api_key=`) | MCP SSE entry point for a server group; returns 404 if slug doesn't exist or is disabled |
| `POST` | `/messages/{slug}/` | — | MCP message relay (handled by the corresponding bundle's `SseServerTransport`) |

### Read-only

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/tools` | JWT Bearer | Lists all registered MCP tools, each with `assigned_server_slug` field |
| `GET` | `/logs` | JWT Bearer | Query call logs, admins see all, regular users only see their own |
| `GET` | `/config` | JWT Bearer | Returns connection config JSON for **all enabled** server groups |
| `POST` | `/keys` | JWT Bearer | Creates an MCP API Key for the current user |

### Server Group Management (`mcp.admin`)

| Method | Path | Description |
|--------|------|-------------|
| `GET`    | `/servers` | Lists all server groups and their current tool count |
| `POST`   | `/servers` | Create new group `{slug, name, description?, max_tools?}` |
| `PATCH`  | `/servers/{id}` | Update name / description / max_tools / is_enabled / sort_order |
| `DELETE` | `/servers/{id}` | Delete group——its tools return to unassigned pool (FK `SET NULL`) |
| `GET`    | `/assignments` | Returns `{ assigned: { slug: [tool_names] }, unassigned: [tool_names] }` |
| `POST`   | `/assignments/move` | Move single tool: `{ tool_name, target_server_id \| null }`; rejects if target is full |
| `POST`   | `/assignments/bulk` | Atomically replace a group of tools' assignments (includes capacity validation) |

---

## Security Considerations

- **API Key shown only once**: Copy immediately after creation; if lost, you must create a new one.
- **Principle of least privilege**: Create different API Keys for different purposes and assign different roles, avoiding one key with excessive permissions.
- **Keys can be revoked anytime**: Delete via Helm's existing `/api/v1/user/tokens/{id}` endpoint or in the frontend.
- **HTTPS in production**: Always use HTTPS in production to prevent API Key leakage in transit (URL parameters appear in access logs).
- **Audit logging**: All tool invocations are logged; admins can check for suspicious activity anytime.

---

## Management Interface

After plugin installation, the **🤖 MCP Access** menu item appears in the sidebar with four tabs:

- **🔑 API Keys** — Create dedicated MCP keys; render independent Claude Desktop config JSON for each enabled server group
- **🗂 Server Groups** (requires `mcp.admin`) — Add/remove/edit server groups, enable/disable, set capacity limits; show "Unassigned Pool" at the bottom where you can move tools between groups via dropdown
- **🛠 Available Tools** — Browse all registered MCP tools, each row shows "Assigned to Server" or "Unassigned" label
- **📋 Call Logs** — View tool invocation history (timestamp, tool name, status, duration, error message), supports filtering by tool name and status

---

## Contributing

This plugin is in Alpha development stage. We welcome:

- Submitting Issues to report problems or suggest features
- Forking the repository for custom development
- Submitting Pull Requests to contribute code

If you have questions, please open a Discussion or Issue on GitHub.
