<template>
  <v-container>
    <v-row class="my-4">
      <v-col cols="12" sm="6" xl="3">
        <v-number-input
          v-model="width"
          control-variant="split"
          density="comfortable"
          hide-details
          label="宽度"
          variant="outlined"
        />
      </v-col>
      <v-col cols="12" sm="6" xl="3">
        <v-number-input
          v-model="height"
          control-variant="split"
          density="comfortable"
          hide-details
          label="高度"
          variant="outlined"
        />
      </v-col>
      <v-col cols="12" md="6" xl="3">
        <v-select
          v-model="format"
          density="comfortable"
          hide-details
          :items="['jpg', 'png', 'webp']"
          label="格式"
          variant="outlined"
        />
      </v-col>
      <v-col cols="12" md="6" xl="3">
        <v-slider
          v-model="quality"
          density="comfortable"
          :disabled="['png'].includes(format)"
          hide-details
          label="质量"
          :max="100"
          :min="1"
          :step="1"
          variant="outlined"
        >
          <template #append>
            <v-number-input
              v-model="quality"
              control-variant="split"
              density="comfortable"
              hide-details
              :step="1"
              variant="outlined"
            />
          </template>
        </v-slider>
      </v-col>
    </v-row>
    <div class="my-4">
      <v-slider v-model="interval" hide-details label="截图间隔（秒）" :max="1" :min="0">
        <template #append>
          <v-number-input
            v-model="interval"
            control-variant="split"
            density="comfortable"
            hide-details
            :precision="null"
            :step="0.1"
            variant="outlined"
          />
        </template>
      </v-slider>
    </div>

    <!-- 监控控制按钮 -->
    <div class="my-4">
      <v-btn
        :color="isMonitoring ? 'error' : 'primary'"
        :prepend-icon="isMonitoring ? 'mdi-stop' : 'mdi-play'"
        size="large"
        @click="toggleMonitoring"
      >
        {{ isMonitoring ? '停止监控' : '开始监控' }}
      </v-btn>
    </div>

    <!-- 截图显示区域 -->
    <img
      v-if="screenshotUrl !== null"
      alt="Screenshot"
      class="my-4"
      :src="screenshotUrl"
      style="max-width: 100%; height: auto"
    />
    <v-alert v-else-if="windowNotFound" border="start" class="my-4" type="warning" variant="tonal">
      <div class="d-flex align-center justify-space-between">
        <span>未检测到终末地窗口，请启动游戏后重新开始监控</span>
        <v-btn color="primary" size="small" variant="tonal" @click="startMonitoring">
          重新开始
        </v-btn>
      </div>
    </v-alert>
    <v-alert v-else-if="!isMonitoring" border="start" class="my-4" type="info" variant="tonal">
      点击"开始监控"按钮开始实时监控终末地窗口
    </v-alert>
    <v-alert v-else border="start" class="my-4" type="info" variant="tonal">
      正在连接终末地窗口...
    </v-alert>
  </v-container>
</template>

<script lang="ts" setup>
import { onUnmounted, ref, watch } from 'vue'

const interval = ref<number>(0.1)
const width = ref<number>(1920)
const height = ref<number>(1080)
const format = ref<string>('jpg')
const quality = ref<number>(75)
const screenshotUrl = ref<string | null>(null)
const isMonitoring = ref<boolean>(false)
const windowNotFound = ref<boolean>(false)

let timer: number | null = null

async function updateScreenshot() {
  const params = new URLSearchParams({
    width: width.value.toString(),
    height: height.value.toString(),
    format: format.value,
    quality: quality.value.toString(),
    timestamp: Date.now().toString(),
  })
  const url = `/api/screenshot?${params.toString()}`

  try {
    const response = await fetch(url)

    // 检查响应状态
    if (!response.ok) {
      // 404 或其他错误，说明窗口不存在
      console.warn('截图失败，窗口可能不存在')
      windowNotFound.value = true
      stopTimer()
      screenshotUrl.value = null
      return
    }

    const dataUrl = await response.json()

    // 检查返回值
    if (dataUrl === null || dataUrl === undefined) {
      // 返回 null，说明窗口不存在
      console.warn('未检测到终末地窗口')
      windowNotFound.value = true
      stopTimer()
      screenshotUrl.value = null
      return
    }

    // 成功获取截图
    windowNotFound.value = false
    screenshotUrl.value = dataUrl
  } catch (error) {
    console.error('截图请求失败:', error)
    windowNotFound.value = true
    stopTimer()
    screenshotUrl.value = null
  }
}

function startTimer() {
  if (timer) clearInterval(timer)
  if (interval.value > 0 && isMonitoring.value) {
    timer = window.setInterval(updateScreenshot, interval.value * 1000)
  }
}

function stopTimer() {
  if (timer) {
    window.clearInterval(timer)
    timer = null
  }
}

function startMonitoring() {
  isMonitoring.value = true
  windowNotFound.value = false
  updateScreenshot() // 立即执行一次
  startTimer()
}

function stopMonitoring() {
  isMonitoring.value = false
  windowNotFound.value = false
  stopTimer()
}

function toggleMonitoring() {
  if (isMonitoring.value) {
    stopMonitoring()
  } else {
    startMonitoring()
  }
}

onUnmounted(() => {
  stopMonitoring()
})

// 监听参数变化，如果正在监控则重启定时器
watch([width, height, format, quality, interval], () => {
  if (isMonitoring.value) {
    startTimer()
  }
})
</script>

<style scoped lang="scss"></style>
