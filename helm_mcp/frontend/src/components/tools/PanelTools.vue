<script setup lang="ts">
import { ref, watch } from 'vue'
import { useHelmSDK } from '../../composables/useHelmSDK'
import { useApiFetch } from '../../composables/useApiFetch'
import { useI18n } from '../../composables/useI18n'
import ToolCard from './ToolCard.vue'

interface MCPTool {
  name: string
  description: string
  input_schema: Record<string, unknown>
  required_permission: string | null
  provider_plugin: string
  assigned_server_slug: string | null
}

const { ready } = useHelmSDK()
const { apiFetch } = useApiFetch()
const { t } = useI18n()

const tools = ref<MCPTool[]>([])
const loading = ref(true)
const errorMsg = ref('')
let loaded = false

async function loadTools() {
  if (loaded) return
  loaded = true
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await apiFetch<MCPTool[]>('/tools')
    tools.value = Array.isArray(data) ? data : []
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

watch(ready, (isReady) => {
  if (isReady) loadTools()
}, { immediate: true })
</script>

<template>
  <div>
    <div v-if="loading" class="empty">{{ t('tools.loading') }}</div>
    <div v-else-if="errorMsg" class="error-msg">{{ t('tools.loadFailed', { msg: errorMsg }) }}</div>
    <template v-else>
      <p style="color:var(--text-muted);font-size:0.88rem;margin-bottom:12px">
        {{ t('tools.count', { n: tools.length }) }}
      </p>
      <div v-if="tools.length === 0" class="empty">{{ t('tools.empty') }}</div>
      <ToolCard v-for="tool in tools" :key="tool.name" :tool="tool" />
    </template>
  </div>
</template>
