import Convert from 'ansi-to-html'
import { onBeforeUnmount, onMounted, ref } from 'vue'

const ansiConverter = new Convert({
  fg: '#FFF',
  bg: '#000',
  newline: false,
  escapeXML: false,
  stream: false,
})

export const logs = ref<string[]>([])
export function clearLogs() {
  logs.value = []
}

let websocket: WebSocket | null = null
let reconnectTimer: number | null = null
const maxLogs = 1000

function connectWebSocket() {
  const url = import.meta.env.VITE_API_BASE_URL || window.location.origin
  const wsUrl = `${url.replace(/^http/, 'ws')}/ws/logs`

  websocket = new WebSocket(wsUrl)

  websocket.addEventListener('open', () => {
    console.log('WebSocket连接已建立')
  })

  websocket.addEventListener('message', (event) => {
    const message = event.data
    // 将ANSI码转换为HTML
    const htmlMessage = ansiConverter.toHtml(message)
    logs.value.push(htmlMessage)

    if (logs.value.length > maxLogs) {
      logs.value = logs.value.slice(-maxLogs)
    }
  })

  websocket.addEventListener('close', () => {
    console.log('WebSocket连接已关闭，尝试重连...')
    websocket = null
    reconnectTimer = window.setTimeout(connectWebSocket, 5000)
  })

  websocket.addEventListener('error', (error) => {
    console.error('WebSocket错误:', error)
  })
}

export function useLogs() {
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
