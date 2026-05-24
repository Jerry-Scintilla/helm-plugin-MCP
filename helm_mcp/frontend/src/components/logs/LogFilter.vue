<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from '../../composables/useI18n'
import HelmSelect from '../ui/HelmSelect.vue'

const emit = defineEmits<{ (e: 'filter-change', toolName: string, status: string): void }>()

const { t } = useI18n()

const toolName = ref('')
const status = ref('')

const statusOptions = computed(() => [
  { value: '',        label: t('logs.filter.allStatus') },
  { value: 'success', label: 'success' },
  { value: 'error',   label: 'error' },
  { value: 'denied',  label: 'denied' },
])

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
      <HelmSelect
        v-model="status"
        :options="statusOptions"
        :aria-label="t('logs.filter.allStatus')"
        min-width="140px"
        @update:modelValue="apply"
      />
      <button class="btn sm" @click="apply">{{ t('logs.filter.refresh') }}</button>
    </div>
  </div>
</template>
