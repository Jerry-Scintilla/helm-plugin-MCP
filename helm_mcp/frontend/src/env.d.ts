/// <reference types="vite/client" />

interface HelmSDKContext {
  token: string
  apiBase: string
}

interface HelmSDK {
  init(callback: (ctx: HelmSDKContext) => void): void
  getToken(): string
  requestTokenRefresh(): void
}

// Augment Window without a module boundary — file has no imports so it's a global script
interface Window {
  HelmSDK: HelmSDK
}
