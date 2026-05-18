<script setup lang="ts">
import { useHelmSDK } from '../../composables/useHelmSDK'
import { useI18n } from '../../composables/useI18n'

export interface LogItem {
  id: number
  user_id: number
  tool_name: string
  status: string
  error_message: string | null
  duration_ms: number | null
  created_at: string
}

defineProps<{ items: LogItem[] }>()

const { locale } = useHelmSDK()
const { t } = useI18n()

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(locale.value === 'zh' ? 'zh-CN' : 'en-US', { hour12: false })
}
</script>

<template>
  <div id="logs-table-wrap">
    <table>
      <thead>
        <tr>
          <th>{{ t('logs.table.time') }}</th>
          <th>{{ t('logs.table.tool') }}</th>
          <th>{{ t('logs.table.userId') }}</th>
          <th>{{ t('logs.table.status') }}</th>
          <th>{{ t('logs.table.duration') }}</th>
          <th>{{ t('logs.table.error') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="items.length === 0">
          <td colspan="6" class="empty">{{ t('logs.table.empty') }}</td>
        </tr>
        <tr v-for="log in items" :key="log.id">
          <td style="white-space:nowrap;color:#7a7870">{{ formatDate(log.created_at) }}</td>
          <td style="color:#c8c5b5">{{ log.tool_name }}</td>
          <td>{{ log.user_id }}</td>
          <td><span class="badge" :class="log.status">{{ log.status }}</span></td>
          <td>{{ log.duration_ms !== null ? log.duration_ms : '—' }}</td>
          <td style="color:#bf6a6a;font-size:0.82rem">{{ log.error_message ?? '' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
