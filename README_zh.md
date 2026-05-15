# helm-plugin-mcp

将 Helm EVE Online 舰队管理系统通过 **Model Context Protocol (MCP)** 完整暴露给大型语言模型。安装此插件后，Claude Desktop、Cursor、cline 等支持 MCP 协议的 AI 工具可以直接操作 Helm 的所有功能——查询角色、管理插件、调用其他插件提供的工具——就像一名拥有访问凭证的真实操作员一样。

> **状态**：Alpha 阶段，暂不提供 Releases。欢迎开发者参与贡献或 Fork 自行拓展功能。

---

## 项目简介

`helm-plugin-mcp` 是 Helm 插件系统与 MCP 兼容 AI 客户端之间的桥梁：

- **内置工具**：提供用户信息查询、角色列表、插件管理、API Key 管理等功能
- **插件扩展性**：其他 Helm 插件只需实现 `MCPToolProvider` 协议即可自动注册 MCP 工具，无需修改本插件代码
- **RBAC 集成**：所有工具均受 Helm 现有权限体系保护，LLM 看不到用户无权访问的工具
- **审计日志**：完整记录每次工具调用的用户、时间、状态和耗时

---

## 功能一览

| 功能 | 说明 |
|------|------|
| **MCP SSE 传输** | 标准 SSE 协议，兼容所有 MCP 客户端 |
| **Helm RBAC 集成** | 工具可见性与执行均受 Helm 权限控制 |
| **独立 API Key** | 每个账号可创建多个 `hlm_` 前缀的 API Key，互不影响，可随时撤销 |
| **插件自动发现** | 实现 `MCPToolProvider` 的插件自动注册工具 |
| **审计日志** | 管理员可查看所有用户的调用历史 |
| **管理界面** | 三标签页侧边栏：API Key 管理、工具浏览器、调用日志 |

---

## 快速开始

### 第一步：安装插件

```bash
# 安装 Python 包（editable 模式便于开发）
pip install -e /path/to/helm-plugin-mcp

# 通过 Helm 管理 API 安装（需要 global.plugin_manage 权限）
curl -X POST http://localhost:8000/api/v1/admin/plugins/install \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"package_name": "helm-plugin-mcp"}'
```

### 第二步：分配权限

在 Helm 管理界面（或通过 API）为需要使用 MCP 的用户角色添加 `mcp.access` 权限。`mcp.admin` 权限用于查看全部审计日志和使用 `helm_manage_plugin`。

### 第三步：创建 API Key

**Web UI**：访问侧边栏 **🤖 MCP 接入** → **🔑 API Keys** 标签页。

**API**：
```bash
curl -X POST http://localhost:8000/api/v1/plugins/helm-mcp/keys \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "claude-desktop"}'
```

响应中的 `api_key` 字段（`hlm_xxx...`）**只出现一次**，请立即复制保存。

### 第四步：配置 AI 客户端

**Claude Desktop**（`~/.claude/claude_desktop_config.json`）：
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

**Cursor / cline**（项目级或全局 MCP 配置）：
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

重启 AI 客户端，即可开始使用 Helm 功能。

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

## 工作原理

```
AI 客户端 (Claude Desktop / Cursor / cline)
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
    └── ...                     ← 任意数量的第三方插件
```

**关键设计：权限在两个层级独立执行**

1. **`list_tools` 阶段**：缺少 `required_permission` 的工具对该用户**静默不可见**，LLM 不会知道管理员工具的存在。
2. **`call_tool` 阶段**：即使客户端绕过 `list_tools` 直接调用，权限仍会被再次检查并拒绝。

---

## 为其他插件添加 MCP 工具

任何 Helm 插件只需三步，即可将自己的功能暴露为 MCP 工具，**无需修改 helm-mcp 的任何代码**。

详细开发指南请参阅：[插件开发指南](./Plugin_Dev_Guide/README.md)

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

## 权限说明

本插件新增两个全局权限，安装时自动写入数据库：

| 权限名 | 说明 |
|--------|------|
| `mcp.access` | 允许通过 MCP 协议连接并调用工具。**用户必须拥有此权限才能使用任何 MCP 功能。** |
| `mcp.admin` | 可查看所有用户的调用日志（普通用户只能看自己的），以及调用 `helm_manage_plugin` 工具。 |

> `global.superuser` 或 `is_superuser=True` 的用户自动拥有所有权限，包括上述两项。

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

---

## 管理界面

插件安装后，侧边栏出现 **🤖 MCP 接入** 菜单项，包含三个标签页：

- **🔑 API 密钥** — 创建专用 MCP 密钥，查看已生成的 Claude Desktop 配置 JSON
- **🛠 可用工具** — 浏览当前所有已注册的 MCP 工具，展示名称、描述、所需权限、来源插件和 Input Schema
- **📋 调用日志** — 查看工具调用历史（时间、工具名、状态、耗时、错误信息），支持按工具名和状态过滤

---

## 文档

| 文档 | 语言 | 说明 |
|------|------|------|
| [README](./README.md) | English | 项目说明（英文） |
| [README_zh](./docs/README_zh.md) | 中文 | 原始完整文档（含详细开发指南） |
| [插件开发指南](./Plugin_Dev_Guide/README.md) | 中文 | Helm 插件完整开发文档 |

---

## 参与贡献

本插件处于 Alpha 开发状态，欢迎：

- 提交 Issue 报告问题或建议功能
- Fork 仓库进行二次开发
- 提交 Pull Request 贡献代码

如有问题，请在 GitHub 上开启 Discussion 或 Issue。