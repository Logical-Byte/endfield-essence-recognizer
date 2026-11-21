/**
 * 自定义能量淤积点管理组合式函数。
 *
 * 自定义地点落盘在后端的 `custom_alluviums.json`（全账号通用），这里维护
 * 模块级单例，供「基质规划」页与自定义设定弹窗共用同一份状态。
 */

import type { CustomAlluvium } from '@/utils/gameData/alluvium'
import { ref } from 'vue'
import { useToast } from '@/composables/useToast'

/** 自定义淤积点列表（模块级单例，所有调用方共享同一份状态） */
const customAlluviums = ref<CustomAlluvium[]>([])

/**
 * 状态版本号。
 *
 * 列表请求是异步的，而保存 / 删除成功后会直接把返回的完整列表写进状态。
 * 用版本号淘汰过期响应：只有最后发起的那次请求才允许写回，否则一次在保存前
 * 发出、保存后才返回的 GET 会把刚保存的条目又抹掉（删除同理）。
 */
let stateVersion = 0

export function useCustomAlluviums() {
  /** 写入共享列表，并让仍在途的列表请求失效 */
  function commitList(list: CustomAlluvium[]) {
    stateVersion++
    customAlluviums.value = list
  }

  /**
   * 从后端获取自定义淤积点列表
   */
  async function fetchCustomAlluviums() {
    const version = ++stateVersion
    try {
      const res = await fetch('/api/custom_alluviums')
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      const list: CustomAlluvium[] = await res.json()
      // 期间发生过保存 / 删除或更新的一次拉取时，这份快照已经过期
      if (version !== stateVersion) return
      customAlluviums.value = list
    } catch (error) {
      console.error('获取自定义淤积点失败:', error)
      // 请求失败时列表会停在旧快照上，必须让用户知道现在看到的可能不是最新数据
      useToast().error('获取自定义淤积点失败，列表可能不是最新的')
    }
  }

  /**
   * 保存（新建或按 ID 覆盖）一条自定义淤积点
   *
   * 本地状态一律以返回值为准：后端会把空 ID 补成稳定 ID。
   */
  async function saveCustomAlluvium(entry: CustomAlluvium) {
    const toast = useToast()
    const res = await fetch('/api/custom_alluviums', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entry),
    })
    if (!res.ok) {
      const msg = `保存自定义淤积点失败: HTTP ${res.status}`
      toast.error(msg)
      throw new Error(msg)
    }
    commitList(await res.json())
  }

  /**
   * 按稳定 ID 删除一条自定义淤积点
   */
  async function deleteCustomAlluvium(id: string) {
    const toast = useToast()
    const res = await fetch('/api/custom_alluviums/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    })
    if (!res.ok) {
      const msg = `删除自定义淤积点失败: HTTP ${res.status}`
      toast.error(msg)
      throw new Error(msg)
    }
    commitList(await res.json())
  }

  return {
    customAlluviums,
    fetchCustomAlluviums,
    saveCustomAlluvium,
    deleteCustomAlluvium,
  }
}
