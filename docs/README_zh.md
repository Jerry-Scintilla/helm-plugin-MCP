# helm-plugin-mcp

将 Helm EVE Online 舰队管理系统通过 **Model Context Protocol (MCP)** 完整暴露给大型语言模型。安装此插件后，Claude Desktop、cursor、cline 等支持 MCP 协议的 AI 工具可以直接操作 Helm 的所有功能——查询角色、管理插件、调用其他插件提供的工具——就像一名拥有访问凭证的真实操作员一样。

---

## 目录

- [功能概述](#功能概述)
- [工作原理](#工作原理)
- [安装](#安装)
- [配置 AI 客户端](#配置-ai-客户端)
- [权限说明](#权限说明)
- [内置工具](#内置工具)
- [管理界面](#管理界面)
- [为其他插件添加 MCP 工具](#为其他插件添加-mcp-工具)
  - [快速上手（三步）](#快速上手三步)
  - [MCPToolDef 参数说明](#mcptooldef-参数说明)
  - [完整示例：舰队行动插件](#完整示例舰队行动插件)
  - [权限联动](#权限联动)
  - [错误处理约定](#错误处理约定)
- [API 端点参考](#api-端点参考)
- [安全注意事项](#安全注意事项)

---

## 功能概述

| 能力 | 说明 |
|------|------|
| **MCP SSE 传输** | 通过标准 SSE 协议接入，兼容所有支持 MCP 的 AI 客户端 |
| **RBAC 权限管理** | 复用 Helm 现有角色/权限体系，每个 API Key 的可用工具取决于账号的实际权限 |
| **独立 API Key 凭证** | 每个账号可创建多个 `hlm_` 前缀的 API Key，互相隔离，可随时撤销 |
| **插件系统扩展** | 其他 Helm 插件实现 `MCPToolProvider` 协议并注册后，工具**自动**出现在 MCP 工具列表中，无需修改本插件任何代码 |
| **调用审计日志** | 每次工具调用写入数据库，管理员可查看所有用户的调用历史 |
| **前端管理界面** | 内置三标签页 UI：API Key 管理、工具浏览器、调用日志 |

---

## 工作原理

```
AI 客户端 (Claude Desktop / cursor / cline)
    │
    │  GET /api/v1/plugins/helm-mcp/sse?api_key=hlm_xxx   ← SSE 长连接
    │  POST /api/v1/plugins/helm-mcp/messages/            ← JSON-RPC 消息
    ▼
FastAPI 路由层
    │  验证 API Key → 加载 User + 权限集合 frozenset
    │  绑定到 ContextVar（当前 SSE 连接隔离）
    ▼
MCP Server（mcp.server.lowlevel.Server）
    ├── list_tools()   按用户权限过滤，返回可用工具列表
    └── call_tool()    派发到对应插件的 call_mcp_tool()，记录审计日志
            │
            ▼
ExtensionRegistry["mcp.tool_provider"]
    ├── CoreToolProvider        ← helm-mcp 内置工具
    ├── FleetActionPlugin       ← 其他插件注册的工具（示例）
    └── ...                     ← 任意数量的第三方插件
```

**关键设计：权限在两个层级独立执行**

1. **`list_tools` 阶段**：缺少 `required_permission` 的工具对该用户**静默不可见**，LLM 不会知道管理员工具的存在。
2. **`call_tool` 阶段**：即使客户端绕过 `list_tools` 直接调用，权限仍会被再次检查并拒绝。

---

## 安装

```bash
# 1. 安装 Python 包（editable 模式便于开发）
pip install -e /path/to/helm-plugin-mcp

# 2. 通过 Helm 管理 API 安装插件（需要 global.plugin_manage 权限）
curl -X POST http://localhost:8000/api/v1/admin/plugins/install \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"package_name": "helm-plugin-mcp"}'

# 3. 验证安装状态
curl http://localhost:8000/api/v1/admin/plugins/helm-mcp/status \
  -H "Authorization: Bearer <your-jwt>"
# 期望: {"status": "enabled", "is_loaded": true, "router_mounted": true}
```

---

## 配置 AI 客户端

### 第一步：为账号分配权限

在 Helm 管理界面（或通过 API）为需要使用 MCP 的用户的角色添加 `mcp.access` 权限。

### 第二步：创建 API Key

访问侧边栏 **🤖 MCP 接入** 页面，或通过 API：

```bash
curl -X POST http://localhost:8000/api/v1/plugins/helm-mcp/keys \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "claude-desktop"}'
```

响应中的 `api_key` 字段（`hlm_xxx...`）**只出现一次**，请立即复制保存。

### 第三步：配置 AI 客户端

**Claude Desktop** (`claude_desktop_config.json`):

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

**cursor / cline**（`.cursor/mcp.json` 或项目级 MCP 配置）:

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

配置完成后重启 AI 客户端，即可在对话中直接使用 Helm 功能。

---

## 权限说明

本插件新增两个全局权限，安装时自动写入数据库：

| 权限名 | 说明 |
|--------|------|
| `mcp.access` | 允许通过 MCP 协议连接并调用工具。**用户必须拥有此权限才能使用任何 MCP 功能。** |
| `mcp.admin` | 可查看所有用户的调用日志（普通用户只能看自己的），以及调用 `helm_manage_plugin` 工具。 |

> `global.superuser` 或 `is_superuser=True` 的用户自动拥有所有权限，包括上述两项。

---

## 内置工具

以下工具由 `CoreToolProvider` 提供，安装插件后立即可用：

| 工具名 | 所需权限 | 说明 |
|--------|----------|------|
| `helm_whoami` | `mcp.access` | 返回当前用户的 id、用户名、角色列表、权限列表 |
| `helm_list_characters` | `mcp.access` | 列出当前用户绑定的所有 EVE Online 角色 |
| `helm_list_plugins` | `mcp.access` | 列出所有已安装插件，支持 `enabled_only` 过滤 |
| `helm_manage_plugin` | `mcp.admin` | 启用或禁用指定插件（`action: "enable"` 或 `"disable"`） |
| `helm_list_my_api_keys` | `mcp.access` | 列出当前用户的 API Key（仅显示前缀，不暴露完整密钥） |
| `helm_create_mcp_api_key` | `mcp.access` | 为当前用户创建新 API Key，完整密钥仅返回一次 |

---

## 管理界面

插件安装后，侧边栏出现 **🤖 MCP 接入** 菜单项，包含三个标签页：

- **🔑 API 密钥** — 创建专用 MCP 密钥，查看已生成的 Claude Desktop 配置 JSON
- **🛠 可用工具** — 浏览当前所有已注册的 MCP 工具，展示名称、描述、所需权限、来源插件和 Input Schema
- **📋 调用日志** — 查看工具调用历史（时间、工具名、状态、耗时、错误信息），支持按工具名和状态过滤

---

## 为其他插件添加 MCP 工具

这是本插件最核心的扩展机制。任何 Helm 插件只需三步，即可将自己的功能暴露为 MCP 工具，**无需修改 helm-mcp 的任何代码**。

### 快速上手（三步）

**第一步：** 在插件的 `plugin.py` 顶部导入协议

```python
from helm_mcp.protocols import MCPToolDef, MCPToolProvider
from app.plugins.registry import extension_registry
```

**第二步：** 让插件类实现 `MCPToolProvider` 协议

```python
class MyPlugin(HelmPlugin, MCPToolProvider):

    def get_mcp_tools(self) -> list[MCPToolDef]:
        """声明本插件提供的工具列表。"""
        return [
            MCPToolDef(
                name="my_tool_name",
                description="向 LLM 说明这个工具做什么",
                input_schema={
                    "type": "object",
                    "properties": {
                        "param_a": {"type": "string", "description": "参数说明"},
                    },
                    "required": ["param_a"],
                },
                required_permission="my-plugin.read",  # None 表示无需额外权限
            ),
        ]

    async def call_mcp_tool(
        self,
        name: str,
        args: dict,
        user: User,
        db: AsyncSession,
    ) -> dict:
        """执行工具调用，返回 JSON 可序列化的 dict。"""
        if name == "my_tool_name":
            param_a = args["param_a"]
            # ... 业务逻辑 ...
            return {"result": "..."}
        raise ValueError(f"Unknown tool: {name}")
```

**第三步：** 在 `on_enable` 钩子中注册

```python
    def on_enable(self, ctx: PluginContext) -> None:
        extension_registry.register("mcp.tool_provider", self, self.name)
        # ... 其他注册逻辑 ...
```

完成。下次 AI 客户端刷新工具列表时，你的工具会自动出现。

---

### MCPToolDef 参数说明

```python
@dataclass
class MCPToolDef:
    name: str                        # 工具的唯一标识符，建议使用 plugin-name_action 格式
    description: str                 # LLM 看到的工具描述，越清晰越好
    input_schema: dict               # 标准 JSON Schema（type=object），描述参数结构
    required_permission: str | None  # Helm 权限名；None 表示只需 mcp.access
```

**`name` 命名建议：** 使用插件名前缀避免与其他插件冲突，例如 `fleet_action_list_fleets`、`srp_submit_claim`。

**`input_schema` 格式：** 必须是合法的 JSON Schema `object` 类型，`properties` 和 `required` 均可为空：

```python
# 无参数工具
input_schema = {"type": "object", "properties": {}, "required": []}

# 有参数工具
input_schema = {
    "type": "object",
    "properties": {
        "fleet_id":  {"type": "integer", "description": "舰队 ID"},
        "include_alts": {"type": "boolean", "description": "是否包含小号，默认 false"},
    },
    "required": ["fleet_id"],
}
```

**`required_permission`：** 传入本插件自己定义的权限名（在 `get_permissions()` 中声明的那些）。缺少此权限的用户在 `list_tools` 阶段就看不到这个工具。

---

### 完整示例：舰队行动插件

以下展示一个假想的 `fleet-action` 插件如何通过 MCP 暴露舰队信息查询和成员踢出功能。

```python
# fleet_action/plugin.py

from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.plugins.base import HelmPlugin, PermissionDef, PluginContext, SidebarItem
from app.plugins.registry import extension_registry
from helm_mcp.protocols import MCPToolDef, MCPToolProvider


class FleetActionPlugin(HelmPlugin, MCPToolProvider):
    name = "fleet-action"
    version = "0.2.0"
    author = "Jerry_Scintilla"
    description = "EVE Online 舰队行动管理"
    helm_sdk_version = ">=1.0,<2.0"

    # ── Helm 插件的常规声明 ────────────────────────────────────────────────

    def get_router(self):
        from fleet_action.routers import router
        return router

    def get_permissions(self) -> list[PermissionDef]:
        return [
            PermissionDef("fleet-action.read",  "global", "查看舰队数据"),
            PermissionDef("fleet-action.manage", "global", "管理舰队成员"),
        ]

    def get_sidebar_items(self) -> list[SidebarItem]:
        return [SidebarItem("舰队行动", "/plugins/fleet-action", "⚔️", order=150)]

    # ── MCPToolProvider 实现 ───────────────────────────────────────────────

    def get_mcp_tools(self) -> list[MCPToolDef]:
        return [
            MCPToolDef(
                name="fleet_action_list_fleets",
                description="列出当前活跃的 EVE Online 舰队，返回舰队 ID、指挥官和成员数。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "corporation_id": {
                            "type": "integer",
                            "description": "按公司 ID 过滤，留空则返回所有舰队",
                        },
                    },
                    "required": [],
                },
                required_permission="fleet-action.read",
            ),
            MCPToolDef(
                name="fleet_action_get_fleet_members",
                description="获取指定舰队的所有成员列表，包括角色名、飞船和位置。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "fleet_id": {
                            "type": "integer",
                            "description": "目标舰队的 fleet_id",
                        },
                    },
                    "required": ["fleet_id"],
                },
                required_permission="fleet-action.read",
            ),
            MCPToolDef(
                name="fleet_action_kick_member",
                description="将指定成员踢出舰队。需要 fleet-action.manage 权限。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "fleet_id":    {"type": "integer", "description": "舰队 ID"},
                        "character_id": {"type": "integer", "description": "要踢出的角色 ID"},
                    },
                    "required": ["fleet_id", "character_id"],
                },
                required_permission="fleet-action.manage",
            ),
        ]

    async def call_mcp_tool(
        self,
        name: str,
        args: dict,
        user: User,
        db: AsyncSession,
    ) -> dict:
        if name == "fleet_action_list_fleets":
            return await self._list_fleets(args, user, db)
        if name == "fleet_action_get_fleet_members":
            return await self._get_fleet_members(args, user, db)
        if name == "fleet_action_kick_member":
            return await self._kick_member(args, user, db)
        raise ValueError(f"Unknown tool: {name}")

    # ── 工具的具体实现 ─────────────────────────────────────────────────────

    async def _list_fleets(self, args, user, db) -> dict:
        from fleet_action.models import Fleet
        stmt = select(Fleet).where(Fleet.is_active == True)
        if corp_id := args.get("corporation_id"):
            stmt = stmt.where(Fleet.corporation_id == corp_id)
        fleets = (await db.execute(stmt)).scalars().all()
        return {
            "fleets": [
                {
                    "fleet_id":    f.fleet_id,
                    "commander":   f.commander_name,
                    "member_count": f.member_count,
                    "created_at":  f.created_at.isoformat(),
                }
                for f in fleets
            ]
        }

    async def _get_fleet_members(self, args, user, db) -> dict:
        from fleet_action.esi import fetch_fleet_members
        members = await fetch_fleet_members(args["fleet_id"])
        return {"fleet_id": args["fleet_id"], "members": members}

    async def _kick_member(self, args, user, db) -> dict:
        from fleet_action.esi import kick_fleet_member
        await kick_fleet_member(args["fleet_id"], args["character_id"])
        return {
            "success": True,
            "fleet_id": args["fleet_id"],
            "kicked_character_id": args["character_id"],
        }

    # ── 生命周期 ───────────────────────────────────────────────────────────

    def on_enable(self, ctx: PluginContext) -> None:
        # 注册到 MCP 扩展点
        extension_registry.register("mcp.tool_provider", self, self.name)
        # 其他注册...
```

注册成功后，AI 对话效果示例：

> **用户：** 帮我看看现在有哪些活跃舰队
>
> **Claude：** *(调用 `fleet_action_list_fleets`)* 目前有 3 支活跃舰队：
> - 舰队 #7823 — 指挥官 Aiko Danuja，14 名成员
> - 舰队 #7891 — 指挥官 Vily，32 名成员
> - ...

---

### 权限联动

`required_permission` 与 Helm RBAC 完全联动：

```
用户角色 → 角色权限 → 工具可见性
────────────────────────────────────
player 角色（默认）
  ├─ mcp.access         → 可见: helm_whoami, helm_list_characters, ...
  └─ fleet-action.read  → 可见: fleet_action_list_fleets, fleet_action_get_fleet_members
                          不可见: fleet_action_kick_member（需要 manage）
                          不可见: helm_manage_plugin（需要 mcp.admin）

fc 角色（假设有 fleet-action.manage）
  └─ fleet-action.manage → 额外可见: fleet_action_kick_member
```

拥有权限的用户在 `list_tools` 时才能看到对应工具。权限不足的调用会被记录为 `denied` 状态并返回错误信息，不会抛出异常影响 MCP 会话。

---

### 错误处理约定

`call_mcp_tool` 中的异常处理规则：

| 情况 | 做法 | MCP 记录状态 |
|------|------|-------------|
| 参数缺失或格式错误 | `raise ValueError("描述")` | `error` |
| 业务逻辑失败（如 ESI 返回错误） | `raise RuntimeError("描述")` | `error` |
| 未知工具名 | `raise ValueError(f"Unknown tool: {name}")` | `error` |
| 权限不足（二次检查） | 交由 MCP server 处理，不需要自行抛出 | `denied` |

工具执行的异常会被 MCP server 捕获，以 `{"error": "...", "detail": "..."}` 格式返回给 LLM，不会中断 MCP 连接。

---

## API 端点参考

所有端点均挂载在 `/api/v1/plugins/helm-mcp/` 下：

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/sse` | API Key (`?api_key=`) | MCP SSE 连接入口，供 AI 客户端使用 |
| `POST` | `/messages/` | — | MCP 消息中继（由 SSE transport 内部管理） |
| `GET` | `/tools` | JWT Bearer | 列出所有可用 MCP 工具（供前端工具浏览器使用） |
| `GET` | `/logs` | JWT Bearer | 查询调用日志，管理员可见全部，普通用户只见自己的 |
| `GET` | `/config` | JWT Bearer | 返回 AI 客户端所需的连接配置 JSON |
| `POST` | `/keys` | JWT Bearer | 为当前用户创建 MCP API Key |

---

## 安全注意事项

- **API Key 只展示一次**：创建后立即复制，丢失后只能重新创建。
- **最小权限原则**：为不同用途创建不同 API Key，并分配不同角色，避免一个 Key 权限过大。
- **Key 可随时撤销**：通过 Helm 现有的 `/api/v1/user/tokens/{id}` 端点删除，或在前端操作。
- **HTTPS**：生产环境务必通过 HTTPS 提供服务，防止 API Key 在传输中泄露（URL 参数会出现在访问日志中）。
- **审计日志**：所有工具调用均有记录，管理员可随时检查是否有异常调用行为。
