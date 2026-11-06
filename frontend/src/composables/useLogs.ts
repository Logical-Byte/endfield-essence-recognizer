import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ansiToHtmlLines } from '@/utils/logLines'

/** 日志的一行：`id` 只用于 `v-for` 的稳定 key，`html` 是已转义并按行自闭合的片段。 */
export interface LogLine {
  id: number
  html: string
}

/**
 * 保留的行数上限。
 *
 * 这里必须按**行**计算，而不是按收到的消息条数：后端一次批量推送最多 32 行，
 * 按条数限流时实际保留量会在 1 行到 32000 行之间浮动，上限形同虚设。
 *
 * 能回看多久取决于日志级别：INFO 下一次完整扫描约 100~150 行，5000 行够回看几十轮；
 * DEBUG 下实测每秒约 15 行，5000 行大约只剩最近 5 分钟。更早的内容在日志文件里始终
 * 完整保留（日志页上的「打开日志文件目录」）。
 */
const MAX_LOG_LINES = 5000

export const logs = ref<LogLine[]>([])

let nextLineId = 0

export function clearLogs() {
  logs.value = []
}

/**
 * 追加一段日志消息，超出上限时从最早的行开始丢弃。
 *
 * @param message 后端 WebSocket 推送的一条原始日志消息（可含多行与 ANSI 颜色）
 */
function appendLogMessage(message: string) {
  const newLines = ansiToHtmlLines(message)
  if (newLines.length === 0) {
    return
  }

  const buffer = logs.value
  for (const html of newLines) {
    nextLineId += 1
    buffer.push({ id: nextLineId, html })
  }

  const overflow = buffer.length - MAX_LOG_LINES
  if (overflow > 0) {
    buffer.splice(0, overflow)
  }
}

let websocket: WebSocket | null = null
let reconnectTimer: number | null = null

function connectWebSocket() {
  const wsProtocol = window.location.protocol.replace('http', 'ws')
  const host = window.location.host
  const wsUrl = `${wsProtocol}//${host}/ws/logs`

  websocket = new WebSocket(wsUrl)

  websocket.addEventListener('open', () => {
    console.log('WebSocket 连接已建立')
    // 后端连上后会先把最近的历史日志整段回放一遍，所以这里先清空，
    // 否则重连一次就重复叠加一份历史，日志量会成倍增长。
    clearLogs()
  })

  websocket.addEventListener('message', (event) => {
    appendLogMessage(event.data)
  })

  websocket.addEventListener('close', () => {
    console.log('WebSocket 连接已关闭，尝试重连...')
    websocket = null
    reconnectTimer = window.setTimeout(connectWebSocket, 5000)
  })

  websocket.addEventListener('error', (error) => {
    console.error('WebSocket 错误:', error)
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
