<template>
  <v-container class="h-100 d-flex flex-column gr-4">
    <div>
      <h1 v-if="false">日志</h1>
      <div class="d-flex flex-row flex-wrap ga-3">
        <v-btn color="primary" @click="startScanning">开始扫描基质</v-btn>
        <v-spacer />
        <v-btn color="error" @click="clearLogs">清空日志</v-btn>
        <v-btn :color="autoScroll ? 'success' : 'warning'" @click="toggleAutoScroll">
          {{ autoScroll ? '自动滚动：开' : '自动滚动：关' }}
        </v-btn>
        <v-tooltip location="bottom" text="日志文件中的日志更全">
          <template #activator="{ props }">
            <v-badge v-bind="props" icon="mdi-help">
              <v-btn color="secondary" @click="openLogsFolder">打开日志文件目录</v-btn>
            </v-badge>
          </template>
        </v-tooltip>
      </div>
    </div>
    <!-- 先用 id 选择器凑合一下,因为用 v-card 上用 ref 绑定的并不是 DOM 元素,而是那个奇妙的 v-card 对象 -->
    <v-card id="log-card" class="flex-grow-1 pa-4 overflow-auto" rounded="lg" variant="outlined">
      <pre v-if="logs.length > 0" class="logs-content text-pre-wrap h-0" v-html="logs.join('')" />
      <pre v-else>暂无日志...</pre>
    </v-card>
  </v-container>
</template>

<script lang="ts" setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { clearLogs, logs } from '@/composables/useLogs'

const autoScroll = ref(true)

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value
}

function startScanning() {
  fetch('/api/start_scanning', { method: 'POST' })
}

function openLogsFolder() {
  fetch('/api/open_logs_folder', { method: 'POST' })
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
