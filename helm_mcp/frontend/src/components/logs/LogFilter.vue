<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{ (e: 'filter-change', toolName: string, status: string): void }>()

const toolName = ref('')
const status = ref('')

function apply() {
  emit('filter-change', toolName.value.trim(), status.value)
}
</script>

<template>
  <div class="card" style="padding:12px 16px">
    <div class="row">
      <span class="label" style="margin:0">筛选：</span>
      <input
        v-model="toolName"
        type="text"
        placeholder="工具名"
        style="width:180px"
        @keyup.enter="apply"
      />
      <select v-model="status" @change="apply">
        <option value="">全部状态</option>
        <option value="success">success</option>
        <option value="error">error</option>
        <option value="denied">denied</option>
      </select>
      <button class="btn sm" @click="apply">刷新</button>
    </div>
  </div>
</template>
