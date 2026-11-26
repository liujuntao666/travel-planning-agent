import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    // 生产构建可把静态资源指向 CDN；未配置时保持同源部署
    base: env.VITE_CDN_BASE || '/',
    plugins: [vue()],
    build: {
      assetsDir: 'assets',
      sourcemap: false,
    },
  }
})
