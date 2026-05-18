<script setup lang="ts">
import { useI18n } from '../../composables/useI18n'

defineProps<{
  tool: {
    name: string
    description: string
    input_schema: Record<string, unknown>
    required_permission: string | null
    provider_plugin: string
  }
}>()

const { t } = useI18n()
</script>

<template>
  <div class="tool-card">
    <div class="tool-name">{{ tool.name }}</div>
    <div class="tool-desc">{{ tool.description }}</div>
    <div class="tool-meta">
      <span v-if="tool.required_permission" class="perm">
        {{ t('tools.perm', { perm: tool.required_permission }) }}
      </span>
      <span v-else style="color:#4a6a50">{{ t('tools.noPerm') }}</span>
      <span>{{ t('tools.source', { plugin: tool.provider_plugin }) }}</span>
    </div>
    <details>
      <summary>{{ t('tools.schema') }}</summary>
      <pre style="margin-top:8px">{{ JSON.stringify(tool.input_schema, null, 2) }}</pre>
    </details>
  </div>
</template>
