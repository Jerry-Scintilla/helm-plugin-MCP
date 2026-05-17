<script setup lang="ts">
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

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}
</script>

<template>
  <div id="logs-table-wrap">
    <table>
      <thead>
        <tr>
          <th>时间</th>
          <th>工具</th>
          <th>用户 ID</th>
          <th>状态</th>
          <th>耗时 (ms)</th>
          <th>错误信息</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="items.length === 0">
          <td colspan="6" class="empty">暂无日志记录</td>
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
