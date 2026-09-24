import { fileURLToPath, URL } from 'node:url'
import Vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// 测试用的独立配置：不复用 vite.config.mts。
//
// 主配置里的 Vuetify / VueDevTools 插件面向浏览器构建，在测试环境既不需要
// 也会拖慢启动；这里只保留跑组件与组合式函数所必需的部分。
// `@` 别名必须在此重新声明——vitest 不会自动继承主配置的 resolve.alias，
// 缺了它任何带 `@/` 导入的模块在测试里都会解析失败。
export default defineConfig({
  plugins: [Vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.{test,spec}.?(c|m)[jt]s?(x)'],
    restoreMocks: true,
  },
})
