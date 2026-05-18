<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '../../composables/useI18n'

const props = defineProps<{
  sseUrl: string
  apiKey?: string
}>()

const { t } = useI18n()

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
    <h3>{{ t('keys.config.title') }}</h3>
    <p style="color:#7a7870;font-size:0.87rem;margin-bottom:10px">
      {{ t('keys.config.hint') }}
    </p>
    <pre>{{ configJson }}</pre>
  </div>
</template>
