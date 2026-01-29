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
    <img
      v-if="screenshotUrl !== null"
      alt="Screenshot"
      class="my-4"
      :src="screenshotUrl"
      style="max-width: 100%; height: auto"
    />
    <v-alert v-else class="my-4" border="start" type="warning" variant="tonal">
      终末地窗口不在前台
    </v-alert>
  </v-container>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'

const interval = ref<number>(0.1)
const width = ref<number>(1920)
const height = ref<number>(1080)
const format = ref<string>('jpg')
const quality = ref<number>(75)
const screenshotUrl = ref<string | null>(null)

let timer: number | null = null

async function updateScreenshot() {
  const params = new URLSearchParams({
    width: width.value.toString(),
    height: height.value.toString(),
    format: format.value,
    quality: quality.value.toString(),
    timestamp: Date.now().toString(),
  })
  const url = `${import.meta.env.VITE_API_BASE_URL}/api/screenshot?${params.toString()}`
  // const oldUrl = screenshotUrl.value
  // fetch(url)
  //   .then((response) => response.blob())
  //   .then((blob) => {
  //     const newUrl = URL.createObjectURL(blob)
  //     screenshotUrl.value = newUrl
  //     // 释放旧的对象URL以防内存泄漏
  //     if (oldUrl) {
  //       URL.revokeObjectURL(oldUrl)
  //     }
  //   })
  //   .catch((error) => {
  //     console.error('Failed to fetch screenshot:', error)
  //   })

  await fetch(url)
    .then((response) => response.json())
    .then((dataUrl) => {
      screenshotUrl.value = dataUrl
    })
}

function startTimer() {
  if (timer) clearInterval(timer)
  if (interval.value > 0) {
    timer = window.setInterval(updateScreenshot, interval.value * 1000)
  }
}

onMounted(() => {
  updateScreenshot() // 初始加载
  startTimer()
})

onUnmounted(() => {
  if (timer) {
    window.clearInterval(timer)
  }
})

watch([width, height, format, quality, interval], startTimer)
</script>

<style scoped lang="scss"></style>
