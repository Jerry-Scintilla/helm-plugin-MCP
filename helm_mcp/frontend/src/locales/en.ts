export default {
  app: {
    title: 'MCP Access',
  },
  tabs: {
    keys: '🔑 API Keys',
    tools: '🛠 Tools',
    logs: '📋 Call Logs',
  },
  keys: {
    loading: 'Loading…',
    configFailed: '(Config load failed, please refresh the page)',
    create: {
      title: 'Create New MCP Key',
      placeholder: 'Key alias, e.g. claude-desktop',
      btn: 'Create Key',
      warning: '⚠️ The full key is shown only once. Copy and save it now:',
      copy: 'Copy',
      copied: 'Copied ✓',
    },
    toast: {
      empty: 'Please enter a key alias',
      copied: 'Copied to clipboard',
      copyFailed: 'Copy failed, please select and copy manually',
      createFailed: 'Creation failed: {msg}',
      requestFailed: 'Request failed: {msg}',
    },
    config: {
      title: 'Connection Config',
      hint: 'Use the following config in MCP-compatible clients like Claude Desktop / Cursor / Cline:',
    },
  },
  tools: {
    loading: 'Loading…',
    loadFailed: 'Failed to load tools: {msg}',
    count: '{n} tools total',
    empty: 'No tools available',
    perm: '🔒 Requires permission: {perm}',
    noPerm: '✓ No extra permissions required',
    source: 'Source plugin: {plugin}',
    schema: 'View Input Schema',
  },
  logs: {
    loading: 'Loading…',
    loadFailed: 'Failed to load logs: {msg}',
    filter: {
      label: 'Filter:',
      toolName: 'Tool name',
      allStatus: 'All statuses',
      refresh: 'Refresh',
    },
    table: {
      time: 'Time',
      tool: 'Tool',
      userId: 'User ID',
      status: 'Status',
      duration: 'Duration (ms)',
      error: 'Error',
      empty: 'No log records',
    },
  },
} as const
