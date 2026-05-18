<script setup lang="ts">
import { useI18n } from '../../composables/useI18n'

export type TabName = 'keys' | 'tools' | 'logs'

const props = defineProps<{ modelValue: TabName }>()
const emit = defineEmits<{ (e: 'update:modelValue', tab: TabName): void }>()

const { t } = useI18n()

const tabs: { name: TabName }[] = [
  { name: 'keys' },
  { name: 'tools' },
  { name: 'logs' },
]
</script>

<template>
  <div class="tabs">
    <div
      v-for="tab in tabs"
      :key="tab.name"
      class="tab"
      :class="{ active: props.modelValue === tab.name }"
      @click="emit('update:modelValue', tab.name)"
    >
      {{ t('tabs.' + tab.name) }}
    </div>
  </div>
</template>
