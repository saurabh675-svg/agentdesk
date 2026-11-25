/// <reference types="vite/client" />

interface Window {
  desktop?: {
    isDesktop: boolean
    apiToken: string
    openFolder: () => Promise<string | null>
    openExternal: (url: string) => Promise<void>
    quit?: () => Promise<boolean>
    restart?: () => Promise<boolean>
    getBackendLog?: (maxLines?: number) => Promise<string>
    openBackendLog?: () => Promise<boolean>
  }
}
