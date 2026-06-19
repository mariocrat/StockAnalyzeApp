import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const root = dirname(fileURLToPath(import.meta.url))
  const env = loadEnv(mode, root, '')
  const appName = env.VITE_APP_NAME || 'AlphaMate'

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
