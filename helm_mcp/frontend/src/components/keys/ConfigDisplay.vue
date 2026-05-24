<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '../../composables/useI18n'

interface ServerConfigEntry {
  slug: string
  name: string
  sse_url: string
  messages_url: string
  tool_count: number
}

const props = defineProps<{
  server: ServerConfigEntry
  apiKey?: string
}>()

const { t } = useI18n()

const configJson = computed(() => {
  const url = props.apiKey
    ? `${props.server.sse_url}?api_key=${props.apiKey}`
    : `${props.server.sse_url}?api_key=YOUR_HLM_API_KEY`

  return JSON.stringify(
    { mcpServers: { [`helm-${props.server.slug}`]: { url, transport: 'sse' } } },
    null,
    2
  )
})
</script>

<template>
  <div class="card">
    <h3>
      {{ t('keys.config.title') }} — {{ server.name }}
      <code style="margin-left:6px;font-size:0.85rem;color:var(--text-muted)">{{ server.slug }}</code>
      <span style="margin-left:8px;color:var(--text-muted);font-weight:normal;font-size:0.85rem">
        {{ t('keys.config.tools', { n: server.tool_count }) }}
      </span>
    </h3>
    <p style="color:#7a7870;font-size:0.87rem;margin-bottom:10px">
      {{ t('keys.config.hint') }}
    </p>
    <pre>{{ configJson }}</pre>
  </div>
</template>
