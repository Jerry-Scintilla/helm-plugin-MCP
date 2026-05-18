export default {
  app: {
    title: 'MCP 接入管理',
  },
  tabs: {
    keys: '🔑 API 密钥',
    tools: '🛠 可用工具',
    logs: '📋 调用日志',
  },
  keys: {
    loading: '加载中…',
    configFailed: '（配置加载失败，请刷新页面）',
    create: {
      title: '创建新 MCP 密钥',
      placeholder: '密钥备注名，如 claude-desktop',
      btn: '创建密钥',
      warning: '⚠️ 完整密钥只显示一次，请立即复制并妥善保存：',
      copy: '复制',
      copied: '已复制 ✓',
    },
    toast: {
      empty: '请输入密钥备注名',
      copied: '已复制到剪贴板',
      copyFailed: '复制失败，请手动选择文字复制',
      createFailed: '创建失败：{msg}',
      requestFailed: '请求失败：{msg}',
    },
    config: {
      title: '连接配置',
      hint: '在 Claude Desktop / cursor / cline 等支持 MCP 的客户端中使用以下配置：',
    },
  },
  tools: {
    loading: '加载中…',
    loadFailed: '工具列表加载失败：{msg}',
    count: '共 {n} 个工具',
    empty: '暂无可用工具',
    perm: '🔒 需要权限: {perm}',
    noPerm: '✓ 无需额外权限',
    source: '来源插件: {plugin}',
    schema: '查看 Input Schema',
  },
  logs: {
    loading: '加载中…',
    loadFailed: '日志加载失败：{msg}',
    filter: {
      label: '筛选：',
      toolName: '工具名',
      allStatus: '全部状态',
      refresh: '刷新',
    },
    table: {
      time: '时间',
      tool: '工具',
      userId: '用户 ID',
      status: '状态',
      duration: '耗时 (ms)',
      error: '错误信息',
      empty: '暂无日志记录',
    },
  },
} as const
