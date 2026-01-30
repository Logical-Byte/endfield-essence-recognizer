import { ref } from 'vue'

export interface UpdateInfo {
  latestVersion: string
  downloadUrl: string
}

const hasNewVersionDialog = ref<boolean>(false)
const isLatestVersionDialog = ref<boolean>(false)
const checkUpdateFailedDialog = ref<boolean>(false)
const currentVersion = ref<string | null>(null)
const updateInfo = ref<UpdateInfo | null>(null)
const updateErrorMessage = ref<string>('')

export function useUpdateChecker() {
  /**
   * 比较版本号
   * 返回 1 表示 v1 > v2, -1 表示 v1 < v2, 0 表示相等
   */
  function compareVersions(v1: string, v2: string): number {
    const parts1 = v1.split('.').map(Number)
    const parts2 = v2.split('.').map(Number)
    const maxLength = Math.max(parts1.length, parts2.length)

    for (let i = 0; i < maxLength; i++) {
      const part1 = parts1[i] || 0
      const part2 = parts2[i] || 0
      if (part1 > part2) return 1
      if (part1 < part2) return -1
    }
    return 0
  }

  /**
   * 检查更新
   * @param showIfLatest 如果已是最新版本，是否显示提示
   */
  async function checkForUpdates(showIfLatest: boolean = false) {
    try {
      // 获取当前版本
      currentVersion.value = await fetch('/api/version').then((res) => res.json())

      if (!currentVersion.value) {
        updateErrorMessage.value = '无法获取当前版本信息'
        checkUpdateFailedDialog.value = true
        return
      }

      // 获取最新版本信息
      updateInfo.value = await fetch(
        `https://cos.yituliu.cn/endfield/endfield-essence-recognizer/version.json?t=${Date.now()}`,
      ).then((res) => res.json())

      if (!updateInfo.value?.latestVersion) {
        updateErrorMessage.value = '无法获取最新版本信息'
        checkUpdateFailedDialog.value = true
        return
      }

      // 比较版本
      if (compareVersions(updateInfo.value.latestVersion, currentVersion.value) > 0) {
        hasNewVersionDialog.value = true
      } else if (showIfLatest) {
        isLatestVersionDialog.value = true
      }
    } catch (error) {
      console.error('检查更新失败：', error)
      updateErrorMessage.value =
        error instanceof Error ? error.message : '网络请求失败，请检查网络连接'
      checkUpdateFailedDialog.value = true
    }
  }

  return {
    // 状态
    hasNewVersionDialog,
    isLatestVersionDialog,
    checkUpdateFailedDialog,
    currentVersion,
    updateInfo,
    updateErrorMessage,
    // 方法
    checkForUpdates,
  }
}
