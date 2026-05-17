<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  current: number
  total: number
  pageSize: number
}>()

const emit = defineEmits<{ (e: 'page-change', page: number): void }>()

const pageCount = computed(() => Math.ceil(props.total / props.pageSize))
</script>

<template>
  <div v-if="pageCount > 1" class="pagination">
    <button
      v-for="page in pageCount"
      :key="page"
      class="page-btn"
      :class="{ active: page === current }"
      @click="emit('page-change', page)"
    >
      {{ page }}
    </button>
  </div>
</template>
