# helm-plugin-mcp

将 Helm EVE Online 舰队管理系统通过 **Model Context Protocol (MCP)** 完整暴露给大型语言模型。安装此插件后，Claude Desktop、Cursor、cline 等支持 MCP 协议的 AI 工具可以直接操作 Helm 的所有功能——查询角色、管理插件、调用其他插件提供的工具——就像一名拥有访问凭证的真实操作员一样。

> **状态**：Alpha 阶段（当前 `0.2.0`），欢迎开发者参与贡献或 Fork 自行拓展功能。

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **MCP SSE 传输** | 标准 SSE 协议，兼容所有 MCP 客户端 |
| **多服务器分组** | 工具按领域拆分到多个逻辑 MCP 服务器（每组 ≤12 个 tool） |
| **Helm RBAC 集成** | 工具可见性与执行均受 Helm 权限控制 |
| **独立 API Key** | 每个账号可创建多个 `hlm_` 前缀的 API Key，互不影响，可随时撤销 |
| **插件自动发现** | 实现 `MCPToolProvider` 的插件自动注册工具 |
| **审计日志** | 完整记录每次工具调用的用户、时间、状态和耗时 |
| **管理界面** | 四标签页侧边栏：API 密钥、服务器分组、工具浏览、调用日志 |

---

## 快速开始

### 安装

```bash
# 1. 安装 Python 包（editable 模式便于开发）
pip install -e /path/to/helm-plugin-mcp

# 2. 通过 Helm 管理 API 安装（需要 global.plugin_manage 权限）
curl -X POST http://localhost:8000/api/v1/admin/plugins/install \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"package_name": "helm-plugin-mcp"}'
```

### 配置步骤

1. **分配权限**：为需要使用 MCP 的用户角色添加 `mcp.access` 权限
2. **创建 API Key**：访问侧边栏 **🤖 MCP 接入** → **🔑 API Keys** 标签页
3. **创建服务器分组**：在 **🗂 服务器分组** 标签页创建分组并分配工具
4. **配置 AI 客户端**：使用 API Keys 标签页生成的配置 JSON

详细配置指南请查阅：[完整文档](./docs/README_zh.md)

---

## 内置工具

```
helm_whoami              — 返回当前用户信息
helm_list_characters    — 列出绑定的 EVE Online 角色
helm_list_plugins       — 列出已安装插件
helm_manage_plugin      — 启用或禁用插件
helm_list_my_api_keys   — 列出个人 API Key
helm_create_mcp_api_key — 创建新 API Key
```

---

## 为其他插件添加工具

任何 Helm 插件只需三步即可将功能暴露为 MCP 工具，无需修改本插件代码：

```python
# 1. 导入协议
from helm_mcp.protocols import MCPToolDef, MCPToolProvider
from app.plugins.registry import extension_registry

# 2. 实现接口
class MyPlugin(HelmPlugin, MCPToolProvider):
    def get_mcp_tools(self) -> list[MCPToolDef]:
        return [MCPToolDef(...)]
    
    async def call_mcp_tool(self, name: str, args: dict, user: User, db: AsyncSession) -> dict:
        # 工具实现...
        return {...}

# 3. 在 on_enable 中注册
def on_enable(self, ctx: PluginContext) -> None:
    extension_registry.register("mcp.tool_provider", self, self.name)
```

详细开发指南：[插件开发](./docs/README_zh.md#为其他插件添加-mcp-工具)

---

## 权限说明

| 权限 | 说明 |
|------|------|
| `mcp.access` | 允许通过 MCP 连接并调用工具（必需） |
| `mcp.admin` | 查看所有用户的调用日志，管理插件 |

---

## 文档

| 文档 | 说明 |
|------|------|
| [完整文档 (中文)](./docs/README_zh.md) | API 端点、详细配置、完整示例、安全指南 |
| [Complete Docs (English)](./docs/README.md) | API endpoints, detailed setup, full examples, security |
| [插件开发指南](./Plugin_Dev_Guide/README.md) | Helm 插件完整开发文档 |

---

## 使用演示

### Github Copilot 与 SRP 补偿申请

以下演示展示了如何通过 Github Copilot 的 MCP 接入，使用 SRP 插件提供的工具进行补偿申请的全流程。

#### 1. 预览补偿申请信息

![Preview Killmail](./docs/screenshot/SRP_1.png)
*Claude 通过 `srp_preview_killmail` 工具预览补偿申请的相关信息*

#### 2. 提交补偿申请

![Submit SRP Request](./docs/screenshot/SRP_2.png)
*使用 `srp_submit_request` 工具提交补偿申请，系统返回申请 ID 和金额*

#### 3. 查看和审批申请

![View Requests](./docs/screenshot/SRP_3.png)
*通过 `srp_list_requests` 和 `srp_review_request` 工具查看申请列表并进行审批*

---

## 参与贡献

本插件处于 Alpha 开发状态，欢迎：

- 提交 Issue 报告问题或建议功能
- Fork 仓库进行二次开发
- 提交 Pull Request 贡献代码

有问题请在 GitHub 上开启 Discussion 或 Issue。
