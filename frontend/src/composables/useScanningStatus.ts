import { onUnmounted, ref } from 'vue'

const isScanning = ref(false)
let statusCheckInterval: number | null = null
let refCount = 0
let pollingEnabled = true

async function checkScanningStatus() {
  try {
    const response = await fetch('/api/scanning_status')
    const status = await response.json()
    isScanning.value = status.is_running
  } catch (error) {
    console.error('Failed to check scanning status:', error)
  }
}

function startStatusPolling() {
  refCount++

  if (statusCheckInterval !== null || !pollingEnabled) {
    return
  }

  checkScanningStatus()
  statusCheckInterval = window.setInterval(checkScanningStatus, 1000)
}

function stopStatusPolling() {
  refCount--

  if (refCount <= 0) {
    refCount = 0
    if (statusCheckInterval !== null) {
      window.clearInterval(statusCheckInterval)
      statusCheckInterval = null
    }
  }
}

export function useScanningStatus(enabled?: boolean) {
  // 从 localStorage 读取 默认禁用
  const storedEnabled = localStorage.getItem('scanningStatusPollingEnabled')
  pollingEnabled = enabled ?? (storedEnabled === 'true')

  if (pollingEnabled) {
    startStatusPolling()
  }

  onUnmounted(() => {
    stopStatusPolling()
  })

  return {
    isScanning,
    pollingEnabled,
  }
}

/**
 * 设置是否启用状态轮询
 */
export function setScanningStatusPolling(enabled: boolean) {
  pollingEnabled = enabled
  localStorage.setItem('scanningStatusPollingEnabled', String(enabled))

  if (enabled && refCount > 0 && statusCheckInterval === null) {
    // 启用
    checkScanningStatus()
    statusCheckInterval = window.setInterval(checkScanningStatus, 1000)
  } else if (!enabled && statusCheckInterval !== null) {
    // 禁用
    window.clearInterval(statusCheckInterval)
    statusCheckInterval = null
  }
}
