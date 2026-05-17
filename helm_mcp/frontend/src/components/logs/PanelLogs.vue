<script setup lang="ts">
import { ref, watch } from 'vue'
import { useHelmSDK } from '../../composables/useHelmSDK'
import { useApiFetch } from '../../composables/useApiFetch'
import LogFilter from './LogFilter.vue'
import LogTable, { type LogItem } from './LogTable.vue'
import Pagination from './Pagination.vue'

interface LogsResponse {
  items: LogItem[]
  total: number
}

const PAGE_SIZE = 50

const { ready } = useHelmSDK()
const { apiFetch } = useApiFetch()

const items = ref<LogItem[]>([])
const total = ref(0)
const page = ref(1)
const toolName = ref('')
const status = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function loadLogs(targetPage = page.value) {
  loading.value = true
  errorMsg.value = ''
  page.value = targetPage

  let qs = `?page=${targetPage}&page_size=${PAGE_SIZE}`
  if (toolName.value) qs += `&tool_name=${encodeURIComponent(toolName.value)}`
  if (status.value)   qs += `&status=${encodeURIComponent(status.value)}`

  try {
    const data = await apiFetch<LogsResponse>(`/logs${qs}`)
    items.value = data.items ?? []
    total.value = data.total ?? 0
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function onFilterChange(newTool: string, newStatus: string) {
  toolName.value = newTool
  status.value = newStatus
  loadLogs(1)
}

watch(ready, (isReady) => {
  if (isReady) loadLogs(1)
}, { immediate: true })
</script>

<template>
  <div>
    <LogFilter @filter-change="onFilterChange" />

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="errorMsg" class="error-msg">日志加载失败：{{ errorMsg }}</div>
    <template v-else>
      <LogTable :items="items" />
      <Pagination
        :current="page"
        :total="total"
        :page-size="PAGE_SIZE"
        @page-change="loadLogs"
      />
    </template>
  </div>
</template>
