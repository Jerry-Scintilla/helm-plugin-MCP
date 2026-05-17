import { ref, readonly } from 'vue'

export type ToastType = 'success' | 'error' | ''

interface ToastState {
  message: string
  type: ToastType
  visible: boolean
}

// Module-level singleton
const state = ref<ToastState>({ message: '', type: '', visible: false })
let hideTimer: ReturnType<typeof setTimeout> | null = null

export function useToast() {
  function showToast(message: string, type: ToastType = '') {
    if (hideTimer !== null) clearTimeout(hideTimer)
    state.value = { message, type, visible: true }
    hideTimer = setTimeout(() => {
      state.value = { ...state.value, visible: false }
      hideTimer = null
    }, 3500)
  }

  return {
    toast: readonly(state),
    showToast,
  }
}
