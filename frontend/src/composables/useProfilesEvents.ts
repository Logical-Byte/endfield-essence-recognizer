/**
 * 订阅后端结构化事件（/ws/events）。
 *
 * 扫描等后台任务完成后，后端推送 profiles_changed 事件，这里收到后
 * 主动刷新 useProfiles 的全局数据，让宝藏基质/基质规划等页面自动更新。
 */

import { onBeforeUnmount, onMounted } from 'vue'

import { useProfiles } from '@/composables/useProfiles'

let websocket: WebSocket | null = null
let reconnectTimer: number | null = null
let fetchInFlight: Promise<void> | null = null

function refreshProfiles() {
  // 合并并发刷新请求，避免事件抖动时重复拉取
  if (fetchInFlight) {
    return fetchInFlight
  }
  fetchInFlight = useProfiles()
    .fetchProfiles()
    .catch(() => {})
    .finally(() => {
      fetchInFlight = null
    })
  return fetchInFlight
}

function handleMessage(event: MessageEvent) {
  try {
    const payload = JSON.parse(event.data as string)
    if (payload.type === 'profiles_changed') {
      void refreshProfiles()
    }
  } catch {
    // 忽略非 JSON 消息（如心跳）
  }
}

function connectWebSocket() {
  const wsProtocol = window.location.protocol.replace('http', 'ws')
  const host = window.location.host
  const wsUrl = `${wsProtocol}//${host}/ws/events`

  websocket = new WebSocket(wsUrl)

  websocket.addEventListener('open', () => {
    console.log('Event WebSocket 连接已建立')
  })

  websocket.addEventListener('message', handleMessage)

  websocket.addEventListener('close', () => {
    console.log('Event WebSocket 连接已关闭，尝试重连...')
    websocket = null
    reconnectTimer = window.setTimeout(connectWebSocket, 5000)
  })

  websocket.addEventListener('error', (error) => {
    console.error('Event WebSocket 错误:', error)
  })
}

export function useProfilesEvents() {
  onMounted(() => {
    if (!websocket) {
      connectWebSocket()
    }
  })

  onBeforeUnmount(() => {
    if (websocket) {
      websocket.close()
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }
  })
}
