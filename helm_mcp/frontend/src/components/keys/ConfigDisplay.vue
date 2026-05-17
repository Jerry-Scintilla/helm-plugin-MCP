<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  sseUrl: string
  apiKey?: string
}>()

const configJson = computed(() => {
  const url = props.apiKey
    ? `${props.sseUrl}?api_key=${props.apiKey}`
    : `${props.sseUrl}?api_key=YOUR_HLM_API_KEY`

  return JSON.stringify(
    { mcpServers: { helm: { url, transport: 'sse' } } },
    null,
    2
  )
})
</script>

<template>
  <div class="card">
    <h3>连接配置</h3>
    <p style="color:#7a7870;font-size:0.87rem;margin-bottom:10px">
      在 Claude Desktop / cursor / cline 等支持 MCP 的客户端中使用以下配置：
    </p>
    <pre>{{ configJson }}</pre>
  </div>
</template>
