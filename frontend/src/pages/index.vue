<template>
  <v-container class="h-100 d-flex flex-column gr-4">
    <div>
      <h1 v-if="false">日志</h1>
      <div class="d-flex flex-row flex-wrap ga-3">
        <v-btn color="primary" @click="startScanning">开始扫描基质</v-btn>
        <v-checkbox
          v-model="autoPageFlip"
          class="mt-0 pt-0"
          color="primary"
          density="compact"
          hide-details
          label="自动翻页"
        />
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
const autoPageFlip = ref(true)

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value
}

// 加载自动翻页设置
async function loadAutoPageFlipSetting() {
  try {
    const response = await fetch('/api/config')
    if (response.ok) {
      const data = await response.json()
      autoPageFlip.value = data.auto_page_flip ?? true
    }
  } catch (error) {
    console.error('加载自动翻页设置失败:', error)
  }
}

// 保存自动翻页设置
async function saveAutoPageFlipSetting() {
  try {
    // 先获取完整配置，然后更新 auto_page_flip 字段
    const getResponse = await fetch('/api/config')
    if (!getResponse.ok) return
    const currentConfig = await getResponse.json()
    currentConfig.auto_page_flip = autoPageFlip.value

    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentConfig),
    })
  } catch (error) {
    console.error('保存自动翻页设置失败:', error)
  }
}

// 监听自动翻页设置变化
watch(autoPageFlip, saveAutoPageFlipSetting)

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
  // 加载自动翻页设置
  loadAutoPageFlipSetting()
})
</script>

<style scoped lang="scss"></style>
