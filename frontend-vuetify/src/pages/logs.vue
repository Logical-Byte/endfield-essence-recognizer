<template>
  <v-container class="h-100 d-flex flex-column gr-4">
    <div>
      <h1>日志</h1>
      <div class="d-flex flex-row gc-3">
        <v-btn color="error" @click="clearLogs">清空日志</v-btn>
        <v-btn :color="autoScroll ? 'success' : 'warning'" @click="toggleAutoScroll">
          {{ autoScroll ? '自动滚动: 开' : '自动滚动: 关' }}
        </v-btn>
        <v-btn color="primary" @click="startScanning">开始扫描基质</v-btn>
      </div>
    </div>
    <!-- 先用 id 选择器凑合一下，因为用 v-card 上用 ref 绑定的并不是 DOM 元素，而是那个奇妙的 v-card 对象 -->
    <v-card id="log-card" class="flex-grow-1 pa-4 overflow-auto">
      <pre
        v-if="logs.length > 0"
        class="logs-content text-pre-wrap h-0"
        v-html="logs.join('')"
      ></pre>
      <pre v-else>暂无日志...</pre>
    </v-card>
  </v-container>
</template>

<script lang="ts" setup>
import { clearLogs, logs } from '@/composables/useLogs'
import { nextTick, onMounted, ref, watch } from 'vue'

const autoScroll = ref(true)

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value
}

function startScanning() {
  fetch(`${import.meta.env.VITE_API_BASE_URL}/api/start_scanning`, { method: 'POST' })
    .then((response) => {
      if (!response.ok) {
        throw new Error('启动扫描失败')
      }
    })
    .catch((error) => {
      console.error('启动扫描时出错:', error)
    })
}

// 监听日志变化，自动滚动
watch(
  logs,
  () => {
    if (autoScroll.value) {
      nextTick(() => {
        // 用 id 选择器凑合一下
        const logsContainer = document.querySelector('#log-card')
        if (logsContainer) {
          logsContainer.scrollTop = logsContainer.scrollHeight
        }
      })
    }
  },
  { deep: true },
)

// 初始滚动到底部
onMounted(() => {
  nextTick(() => {
    // 用 id 选择器凑合一下
    const logsContainer = document.querySelector('#log-card')
    if (logsContainer) {
      logsContainer.scrollTop = logsContainer.scrollHeight
      console.log('日志页面已加载，滚动到底部')
    }
  })
})
</script>

<style scoped lang="scss"></style>
