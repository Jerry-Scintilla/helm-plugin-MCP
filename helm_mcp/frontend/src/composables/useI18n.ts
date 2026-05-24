import { useHelmSDK } from './useHelmSDK'
import zh from '../locales/zh'
import en from '../locales/en'

const messages: Record<string, unknown> = { zh, en }

function getNestedValue(obj: Record<string, unknown>, key: string): string {
  const value = key.split('.').reduce<unknown>((acc, k) => {
    if (acc !== null && typeof acc === 'object') return (acc as Record<string, unknown>)[k]
    return undefined
  }, obj)
  return typeof value === 'string' ? value : key
}

export function useI18n() {
  const { locale } = useHelmSDK()

  function t(key: string, params?: Record<string, string | number>): string {
    const dict = messages[locale.value] ?? messages.zh
    let text = getNestedValue(dict as unknown as Record<string, unknown>, key)
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        text = text.replace(`{${k}}`, String(v))
      }
    }
    return text
  }

  return { t }
}
