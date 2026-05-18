/// <reference types="vite/client" />

interface HelmSDKContext {
  token: string
  apiBase: string
  locale?: 'zh' | 'en'
}

interface HelmSDK {
  init(callback: (ctx: HelmSDKContext) => void): void
  getToken(): string
  getLocale(): 'zh' | 'en'
  requestTokenRefresh(): void
}

// Augment Window without a module boundary — file has no imports so it's a global script
interface Window {
  HelmSDK: HelmSDK
}
