<script setup lang="ts">
export type TabName = 'keys' | 'tools' | 'logs'

const props = defineProps<{ modelValue: TabName }>()
const emit = defineEmits<{ (e: 'update:modelValue', tab: TabName): void }>()

const tabs: { name: TabName; label: string }[] = [
  { name: 'keys',  label: '🔑 API 密钥' },
  { name: 'tools', label: '🛠 可用工具' },
  { name: 'logs',  label: '📋 调用日志' },
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
      {{ tab.label }}
    </div>
  </div>
</template>
