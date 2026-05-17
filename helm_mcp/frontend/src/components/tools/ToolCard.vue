<script setup lang="ts">
defineProps<{
  tool: {
    name: string
    description: string
    input_schema: Record<string, unknown>
    required_permission: string | null
    provider_plugin: string
  }
}>()
</script>

<template>
  <div class="tool-card">
    <div class="tool-name">{{ tool.name }}</div>
    <div class="tool-desc">{{ tool.description }}</div>
    <div class="tool-meta">
      <span v-if="tool.required_permission" class="perm">
        🔒 需要权限: {{ tool.required_permission }}
      </span>
      <span v-else style="color:#4a6a50">✓ 无需额外权限</span>
      <span>来源插件: {{ tool.provider_plugin }}</span>
    </div>
    <details>
      <summary>查看 Input Schema</summary>
      <pre style="margin-top:8px">{{ JSON.stringify(tool.input_schema, null, 2) }}</pre>
    </details>
  </div>
</template>
