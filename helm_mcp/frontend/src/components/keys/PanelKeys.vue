<script setup lang="ts">
import { ref, watch } from 'vue'
import { useHelmSDK } from '../../composables/useHelmSDK'
import { useApiFetch } from '../../composables/useApiFetch'
import { useI18n } from '../../composables/useI18n'
import KeyCreateForm from './KeyCreateForm.vue'
import ConfigDisplay from './ConfigDisplay.vue'

interface ServerConfigEntry {
  slug: string
  name: string
  sse_url: string
  messages_url: string
  tool_count: number
}
interface MCPConfig {
  auth_param: string
  auth_prefix: string
  protocol_version: string
  servers: ServerConfigEntry[]
}

const { ready } = useHelmSDK()
const { apiFetch } = useApiFetch()
const { t } = useI18n()

const servers = ref<ServerConfigEntry[]>([])
const loaded = ref(false)
const lastCreatedKey = ref<string | undefined>()

async function loadConfig() {
  try {
    const cfg = await apiFetch<MCPConfig>('/config')
    servers.value = cfg.servers || []
  } catch {
    servers.value = []
  } finally {
    loaded.value = true
  }
}

watch(ready, (isReady) => {
  if (isReady) loadConfig()
}, { immediate: true })

function onKeyCreated(apiKey: string) {
  lastCreatedKey.value = apiKey
}
</script>

<template>
  <div>
    <KeyCreateForm @key-created="onKeyCreated" />

    <div v-if="!loaded" class="card"><pre>{{ t('keys.loading') }}</pre></div>
    <template v-else>
      <div v-if="servers.length === 0" class="card">
        <p>{{ t('keys.config.noServers') }}</p>
      </div>
      <ConfigDisplay
        v-for="s in servers"
        :key="s.slug"
        :server="s"
        :api-key="lastCreatedKey"
      />
    </template>
  </div>
</template>
