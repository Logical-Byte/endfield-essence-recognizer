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

export function useCustomAlluviums() {
  /**
   * 从后端获取自定义淤积点列表
   */
  async function fetchCustomAlluviums() {
    try {
      const res = await fetch('/api/custom_alluviums')
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      customAlluviums.value = await res.json()
    } catch (error) {
      console.error('获取自定义淤积点失败:', error)
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
    customAlluviums.value = await res.json()
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
    customAlluviums.value = await res.json()
  }

  return {
    customAlluviums,
    fetchCustomAlluviums,
    saveCustomAlluvium,
    deleteCustomAlluvium,
  }
}
