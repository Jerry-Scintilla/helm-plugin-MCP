<script setup lang="ts">
import { useToast } from '../../composables/useToast'

const { toast } = useToast()
</script>

<template>
  <Transition name="toast-fade">
    <div v-if="toast.visible" class="toast" :class="toast.type || undefined">
      {{ toast.message }}
    </div>
  </Transition>
</template>

<style scoped>
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.2s;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
}
</style>
