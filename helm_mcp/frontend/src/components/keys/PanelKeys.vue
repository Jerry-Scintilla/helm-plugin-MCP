<script setup lang="ts">
import { ref, watch } from 'vue'
import { useHelmSDK } from '../../composables/useHelmSDK'
import { useApiFetch } from '../../composables/useApiFetch'
import KeyCreateForm from './KeyCreateForm.vue'
import ConfigDisplay from './ConfigDisplay.vue'

interface MCPConfig { sse_url: string }

const { ready } = useHelmSDK()
const { apiFetch } = useApiFetch()

const sseUrl = ref('')
const lastCreatedKey = ref<string | undefined>()

async function loadConfig() {
  try {
    const cfg = await apiFetch<MCPConfig>('/config')
    sseUrl.value = cfg.sse_url
  } catch {
    sseUrl.value = ''
  }
}

// Load config once the SDK handshake completes
watch(ready, (isReady) => {
  if (isReady) loadConfig()
}, { immediate: true })

function onKeyCreated(apiKey: string) {
  lastCreatedKey.value = apiKey
}
</script>

<template>
  <KeyCreateForm @key-created="onKeyCreated" />
  <ConfigDisplay
    v-if="sseUrl"
    :sse-url="sseUrl"
    :api-key="lastCreatedKey"
  />
  <div v-else class="card">
    <pre>{{ sseUrl === '' ? '加载中…' : '（配置加载失败，请刷新页面）' }}</pre>
  </div>
</template>
