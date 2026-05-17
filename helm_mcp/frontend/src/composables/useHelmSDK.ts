import { ref, readonly } from 'vue'

// Module-level singletons — shared across all composable calls
const token = ref<string | null>(null)
const apiBase = ref<string | null>(null)
const ready = ref(false)
let initCalled = false

export function useHelmSDK() {
  function init() {
    if (initCalled) return
    initCalled = true

    window.HelmSDK.init((ctx) => {
      token.value = ctx.token
      apiBase.value = ctx.apiBase
      ready.value = true
    })

    window.addEventListener('message', (e: MessageEvent) => {
      if (e.data?.type === 'helm:token:refreshed') {
        token.value = e.data.token as string
      }
    })
  }

  return {
    init,
    ready: readonly(ready),
    token: readonly(token),
    apiBase: readonly(apiBase),
  }
}
