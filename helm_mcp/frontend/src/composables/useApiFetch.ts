import { useHelmSDK } from './useHelmSDK'
import { useToast } from './useToast'

const PLUGIN_PREFIX = '/api/v1/plugins/helm-mcp'

export function useApiFetch() {
  const { token, apiBase } = useHelmSDK()
  const { showToast } = useToast()

  async function apiFetch<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Authorization': `Bearer ${token.value}`,
      'Content-Type': 'application/json',
      ...(opts.headers as Record<string, string> | undefined),
    }

    const res = await fetch(`${apiBase.value}${PLUGIN_PREFIX}${path}`, {
      ...opts,
      headers,
    })

    if (res.status === 401) {
      showToast('登录已过期，请刷新页面重新登录', 'error')
    }

    return res.json() as Promise<T>
  }

  return { apiFetch }
}
