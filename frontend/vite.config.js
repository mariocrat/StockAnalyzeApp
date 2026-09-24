import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const root = dirname(fileURLToPath(import.meta.url))
  const env = loadEnv(mode, root, '')
  if (env.VITE_ANDROID_OAUTH_APP_SCHEME === 'com.mariocrat.stockanalyze.debug') {
    const required = ['VITE_KAKAO_REST_API_KEY', 'VITE_NAVER_CLIENT_ID', 'VITE_KAKAO_REDIRECT_URI', 'VITE_NAVER_REDIRECT_URI']
    const missing = required.filter(key => !env[key]?.trim())
    if (missing.length) throw new Error(`Debug OAuth build requires: ${missing.join(', ')}`)
  }
  const appName = env.VITE_APP_NAME || 'StockBoda'

  return {
    plugins: [
      react(),
      {
        name: 'alphamate-html-branding',
        transformIndexHtml(html) {
          return html.replaceAll('%APP_TITLE%', appName)
        },
      },
    ],
  }
})
