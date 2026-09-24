import { ref, watch } from 'vue'

export interface UpdateInfo {
  latestVersion: string
  downloadUrl: string
  packageType?: string
  size?: number | null
  fullSize?: number | null
}

export interface CheckForUpdatesOptions {
  /** 后台自动检查时不弹出失败提示，避免启动阶段打扰用户 */
  silent?: boolean
  /** 自动检查可设置超时，超时后直接放弃本次检查 */
  timeoutMs?: number
}

const hasNewVersionDialog = ref<boolean>(false)
const isLatestVersionDialog = ref<boolean>(false)
const checkUpdateFailedDialog = ref<boolean>(false)
const updateProgressDialog = ref<boolean>(false)
const isUpdating = ref<boolean>(false)
const currentVersion = ref<string | null>(null)
const updateInfo = ref<UpdateInfo | null>(null)
const updateErrorMessage = ref<string>('')

// 下载进度状态
const downloadProgress = ref<number>(0)
const downloadSpeed = ref<number>(0)
const downloadedSize = ref<number>(0)
const totalSize = ref<number>(0)
const totalKnown = ref<boolean>(false)
const selectedFlow = ref<string>('cn_yituliu')
const selectedMirror = ref<string>('github')
const proxyEnabled = ref<boolean>(false)
const proxyPort = ref<string>('7890')
const showProxyInput = ref<boolean>(false)
const downloadFailed = ref<boolean>(false)
const downloadErrorMessage = ref<string>('')

// SHA-256 校验失败状态
const sha256MismatchDialog = ref<boolean>(false)
const sha256Expected = ref<string>('')
const sha256Actual = ref<string>('')

let progressWs: WebSocket | null = null

/** 重置前端进度状态，每次新下载开始前调用 */
function resetProgressState() {
  downloadProgress.value = 0
  downloadSpeed.value = 0
  downloadedSize.value = 0
  totalSize.value = 0
  totalKnown.value = false
}

export function useUpdateChecker() {
  let restartTimer: ReturnType<typeof setTimeout> | null = null
  let isRestarting = false

  // 监听镜像源和代理变化，使用防抖避免多次触发
  watch([selectedMirror, proxyEnabled, proxyPort], async () => {
    if (!isUpdating.value || !updateProgressDialog.value || isRestarting) return

    // 清除之前的定时器
    if (restartTimer) {
      clearTimeout(restartTimer)
    }

    // 500ms 防抖
    restartTimer = setTimeout(async () => {
      isRestarting = true
      const cancelled = await cancelDownloadInternal()
      // 只有在确实取消成功时才重启，避免无下载任务时的误操作
      if (cancelled) {
        await new Promise((resolve) => setTimeout(resolve, 1500))
        await installUpdate()
      }
      isRestarting = false
      restartTimer = null
    }, 500)
  })

  /**
   * 检查更新
   * @param showIfLatest 如果已是最新版本，是否显示提示
   */
  async function checkForUpdates(
    showIfLatest: boolean = false,
    options: CheckForUpdatesOptions = {},
  ) {
    const controller = options.timeoutMs ? new AbortController() : null
    const timeoutId = controller
      ? window.setTimeout(() => controller.abort(), options.timeoutMs)
      : null

    try {
      // 调用后端 API 检查更新
      const response = await fetch('/api/update/check', { signal: controller?.signal })
      const result = await response.json()

      // 后端现在保证：有错误时 has_update=false 且 error=string
      // 没有错误时 has_update=false 且 error=null
      if (result.error) {
        if (options.silent) {
          console.warn('后台检查更新失败：', result.error)
          return
        }
        updateErrorMessage.value = result.error
        checkUpdateFailedDialog.value = true
        return
      }

      // 获取当前版本
      const versionResponse = await fetch('/api/version')
      currentVersion.value = await versionResponse.json()

      if (result.has_update && result.update_info) {
        selectedFlow.value = result.update_info.source || selectedFlow.value
        updateInfo.value = {
          latestVersion: result.update_info.version,
          downloadUrl: result.update_info.download_url,
          packageType: result.update_info.package_type,
          size: result.update_info.size,
          fullSize: result.update_info.full_size,
        }
        hasNewVersionDialog.value = true
      } else if (showIfLatest) {
        isLatestVersionDialog.value = true
      }
    } catch (error) {
      console.error('检查更新失败：', error)
      if (options.silent) return
      updateErrorMessage.value =
        error instanceof Error ? error.message : '网络请求失败，请检查网络连接'
      checkUpdateFailedDialog.value = true
    } finally {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId)
      }
    }
  }

  /**
   * 连接进度 WebSocket
   */
  function connectProgressWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/update/progress`
    progressWs = new WebSocket(wsUrl)

    progressWs.addEventListener('message', (event) => {
      const data = JSON.parse(event.data)
      downloadedSize.value = data.downloaded
      totalSize.value = data.total
      totalKnown.value = data.total_known
      downloadSpeed.value = data.speed
      downloadProgress.value = data.progress
    })

    progressWs.addEventListener('error', () => {
      progressWs?.close()
      progressWs = null
    })
  }

  /**
   * 断开进度 WebSocket
   */
  function disconnectProgressWebSocket() {
    if (progressWs) {
      progressWs.close()
      progressWs = null
    }
  }

  /**
   * 内部取消下载（不关闭对话框，用于重启下载）
   * @returns 是否确实取消了一个活跃的下载任务
   */
  async function cancelDownloadInternal(): Promise<boolean> {
    try {
      const response = await fetch('/api/update/cancel', { method: 'POST' })
      const result = await response.json()
      if (result.success) {
        disconnectProgressWebSocket()
      }
      return result.success
    } catch (error) {
      console.error('取消下载失败：', error)
      return false
    }
  }

  /**
   * 取消下载（用户主动取消，关闭对话框）
   */
  async function cancelDownload() {
    // 先清除定时器，防止 watch 触发重启
    if (restartTimer) {
      clearTimeout(restartTimer)
      restartTimer = null
    }
    isRestarting = false

    try {
      await fetch('/api/update/cancel', { method: 'POST' })
    } catch (error) {
      console.error('取消下载失败：', error)
    } finally {
      disconnectProgressWebSocket()
      updateProgressDialog.value = false
      isUpdating.value = false
    }
  }

  /**
   * 执行更新下载和安装
   * @param skipVerify 是否跳过 SHA-256 校验
   */
  async function installUpdate(skipVerify: boolean = false) {
    try {
      isUpdating.value = true
      downloadFailed.value = false
      downloadErrorMessage.value = ''
      sha256MismatchDialog.value = false
      hasNewVersionDialog.value = false
      updateProgressDialog.value = true

      // 重置进度状态，避免看到上一轮残留值
      resetProgressState()

      // 保存配置：先 GET 当前配置，合并更新字段后 POST，避免覆盖用户其他设置
      const proxyUrl = proxyEnabled.value ? `http://127.0.0.1:${proxyPort.value}` : ''
      const currentConfigRes = await fetch('/api/config')
      const currentConfig = await currentConfigRes.json()
      currentConfig.update_github_mirror = selectedMirror.value
      currentConfig.update_mirror = selectedMirror.value
      currentConfig.update_proxy = proxyUrl
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentConfig),
      })

      connectProgressWebSocket()

      const response = await fetch('/api/update/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skip_verify: skipVerify }),
      })
      const result = await response.json()

      if (!result.success) {
        disconnectProgressWebSocket()
        if (result.error === 'sha256_mismatch') {
          // SHA-256 校验失败，弹出让用户选择是否继续
          sha256Expected.value = result.sha256_expected || ''
          sha256Actual.value = result.sha256_actual || ''
          sha256MismatchDialog.value = true
        } else {
          downloadFailed.value = true
          downloadErrorMessage.value = result.error || '更新失败'
        }
      }
    } catch (error) {
      disconnectProgressWebSocket()
      downloadFailed.value = true
      downloadErrorMessage.value = error instanceof Error ? error.message : '更新失败'
    } finally {
      isUpdating.value = false
    }
  }

  /** 用户确认跳过 SHA-256 校验继续安装 */
  async function forceInstall() {
    sha256MismatchDialog.value = false
    await installUpdate(true)
  }

  /** 用户取消 SHA-256 校验失败后的安装 */
  function cancelSha256Mismatch() {
    sha256MismatchDialog.value = false
    updateProgressDialog.value = false
  }

  return {
    // 状态
    hasNewVersionDialog,
    isLatestVersionDialog,
    checkUpdateFailedDialog,
    updateProgressDialog,
    isUpdating,
    currentVersion,
    updateInfo,
    updateErrorMessage,
    downloadProgress,
    downloadSpeed,
    downloadedSize,
    totalSize,
    totalKnown,
    selectedFlow,
    selectedMirror,
    proxyEnabled,
    proxyPort,
    showProxyInput,
    downloadFailed,
    downloadErrorMessage,
    sha256MismatchDialog,
    sha256Expected,
    sha256Actual,
    // 方法
    checkForUpdates,
    installUpdate,
    forceInstall,
    cancelSha256Mismatch,
    cancelDownload,
  }
}
