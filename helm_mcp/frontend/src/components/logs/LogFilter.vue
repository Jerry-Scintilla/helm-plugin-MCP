<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from '../../composables/useI18n'

const emit = defineEmits<{ (e: 'filter-change', toolName: string, status: string): void }>()

const { t } = useI18n()

const toolName = ref('')
const status = ref('')

function apply() {
  emit('filter-change', toolName.value.trim(), status.value)
}
</script>

<template>
  <div class="card" style="padding:12px 16px">
    <div class="row">
      <span class="label" style="margin:0">{{ t('logs.filter.label') }}</span>
      <input
        v-model="toolName"
        type="text"
        :placeholder="t('logs.filter.toolName')"
        style="width:180px"
        @keyup.enter="apply"
      />
      <select v-model="status" @change="apply">
        <option value="">{{ t('logs.filter.allStatus') }}</option>
        <option value="success">success</option>
        <option value="error">error</option>
        <option value="denied">denied</option>
      </select>
      <button class="btn sm" @click="apply">{{ t('logs.filter.refresh') }}</button>
    </div>
  </div>
</template>
