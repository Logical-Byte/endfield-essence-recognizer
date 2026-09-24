/**
 * 自定义基质管理组合式函数。
 *
 * 管理自定义基质的 CRUD 操作，包括获取、保存、删除等。
 */

import type { TreasureMatrixEntry } from '@/composables/useProfiles'
import type { CustomStat } from '@/utils/gameData/weapon'
import { computed, ref } from 'vue'
import { useProfiles } from '@/composables/useProfiles'
import { useToast } from '@/composables/useToast'
import { useWeaponStats } from '@/composables/useWeaponStats'
import { useStaticData } from '@/utils/gameData/staticData'
import {
  createCustomStatId,
  fallbackCustomStatName,
  findCustomStat,
  toCustomStatId,
} from '@/utils/gameData/weapon'

/** 自定义宝藏基质属性配置列表（模块级单例，所有调用方共享同一份状态） */
const customStats = ref<CustomStat[]>([])

export function useCustomStats() {
  const {
    updateTreasureMatrix,
    addTreasureMatrixEntry,
    removeTreasureMatrixEntry,
    updateWeaponPriority,
  } = useProfiles()
  const { weaponsMap } = useStaticData()
  const { isWeaponOwned, isCustomEntry } = useWeaponStats()

  /** 自定义基质条目列表，用于武器总览展示 */
  const customMatrixEntries = computed(() => {
    return customStats.value.map((stat, index) => ({
      syntheticId: toCustomStatId(stat),
      displayName: stat.name || fallbackCustomStatName(index),
      index,
      skillStatId: stat.skill,
    }))
  })

  /**
   * 从后端获取配置中的自定义宝藏基质属性列表
   */
  async function fetchCustomStats() {
    try {
      const res = await fetch('/api/config')
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      const config = await res.json()
      customStats.value = config.treasure_essence_stats || []
    } catch (error) {
      console.error('获取自定义宝藏基质配置失败:', error)
    }
  }

  /**
   * 将自定义宝藏基质配置保存到后端
   */
  async function postCustomStatsUpdate(stats?: CustomStat[]) {
    const toast = useToast()
    const getRes = await fetch('/api/config')
    if (!getRes.ok) {
      const msg = `获取配置失败: HTTP ${getRes.status}`
      toast.error(msg)
      throw new Error(msg)
    }
    const currentConfig = await getRes.json()
    currentConfig.treasure_essence_stats = stats ?? customStats.value
    const postRes = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentConfig),
    })
    if (!postRes.ok) {
      const msg = `保存自定义基质配置失败: HTTP ${postRes.status}`
      toast.error(msg)
      throw new Error(msg)
    }
  }

  /**
   * 保存自定义基质（新建或编辑）
   *
   * 一律"先请求成功、再更新本地状态"：本地状态是后端返回值的投影，
   * 中途失败时界面保持修改前的样子，不需要回滚。
   */
  async function saveCustomEntry(params: {
    weaponId: string
    name: string
    attribute: string | null
    secondary: string | null
    skill: string | null
    affix1: number
    affix2: number
    affix3: number
    priority: number
    isOwned: boolean
    matrixEntryByWeaponId: ReadonlyMap<string, TreasureMatrixEntry>
    treasureMatrix: readonly TreasureMatrixEntry[]
  }) {
    const {
      weaponId,
      name,
      attribute,
      secondary,
      skill,
      affix1,
      affix2,
      affix3,
      priority,
      isOwned,
      matrixEntryByWeaponId,
      treasureMatrix,
    } = params

    if (weaponId === '__new_custom__') {
      const newEntry: CustomStat = {
        id: createCustomStatId(),
        name: name || fallbackCustomStatName(customStats.value.length),
        attribute,
        secondary,
        skill,
      }

      await postCustomStatsUpdate([...customStats.value, newEntry])

      // 只有标记为"已拥有"时才写入 profile
      if (isOwned) {
        await addTreasureMatrixEntry({
          weapon_id: toCustomStatId(newEntry),
          weapon_name: newEntry.name!,
          affix1_level: affix1,
          affix2_level: affix2,
          affix3_level: affix3,
          priority,
          include_in_calculation: true,
        })
      }
    } else if (isCustomEntry(weaponId)) {
      const found = findCustomStat(weaponId, customStats.value)
      if (found) {
        const tempStats = [...customStats.value]
        tempStats[found.index] = { ...found.stat, name, attribute, secondary, skill }
        await postCustomStatsUpdate(tempStats)
      }

      // 更新 profile 中的等级和优先级：先构造新数组再提交，不改动本地对象
      const entry = matrixEntryByWeaponId.get(weaponId)
      if (entry) {
        const nextMatrix = treasureMatrix.map((item) =>
          item.weapon_id === weaponId
            ? {
                ...item,
                weapon_name: name,
                affix1_level: affix1,
                affix2_level: affix2,
                affix3_level: affix3,
                priority,
              }
            : item,
        )
        await updateTreasureMatrix(nextMatrix)
        await updateWeaponPriority(weaponId, priority)
      }
    }

    await fetchCustomStats()
  }

  /**
   * 确认删除自定义基质
   *
   * 稳定 ID 让删除退化为一次普通的过滤：其余条目的标识不受影响，
   * 无需重写 profile 中的任何引用。
   */
  async function confirmDeleteCustomEntry(params: {
    id: string
    treasureMatrix: readonly TreasureMatrixEntry[]
  }) {
    const { id, treasureMatrix } = params
    const found = findCustomStat(id, customStats.value)
    if (!found) return

    const targetId = toCustomStatId(found.stat)
    const newMatrix = treasureMatrix.filter((e) => e.weapon_id !== targetId && e.weapon_id !== id)
    const tempStats = customStats.value.filter((_, i) => i !== found.index)

    await updateTreasureMatrix(newMatrix)
    // 清理 weapon_priorities 中的幽灵键（priority=0 时后端会 pop 该键）
    await updateWeaponPriority(targetId, 0)
    await postCustomStatsUpdate(tempStats)
    await fetchCustomStats()
  }

  /**
   * 非自定义基质：从基质配置中移除
   */
  async function removeNonCustomEntry(weaponId: string) {
    await removeTreasureMatrixEntry(weaponId)
  }

  /**
   * 切换武器拥有状态（网格右键 / 详情弹窗共用）
   */
  async function toggleWeaponOwnership(weaponId: string) {
    if (isWeaponOwned(weaponId)) {
      await removeTreasureMatrixEntry(weaponId)
    } else {
      // 自定义条目使用配置中的名称，普通武器使用 weaponsMap 中的名称
      let weaponName: string
      if (isCustomEntry(weaponId)) {
        const found = findCustomStat(weaponId, customStats.value)
        weaponName = found ? found.stat.name || fallbackCustomStatName(found.index) : '自定义基质'
      } else {
        const weapon = weaponsMap.value.get(weaponId)
        weaponName = weapon?.name || weaponId
      }
      await addTreasureMatrixEntry({
        weapon_id: weaponId,
        weapon_name: weaponName,
        affix1_level: 1,
        affix2_level: 1,
        affix3_level: 1,
        include_in_calculation: true,
      })
    }
  }

  // 导出 updateWeaponPriority 以便外部使用
  return {
    // 状态
    customStats,
    customMatrixEntries,

    // 操作方法
    fetchCustomStats,
    postCustomStatsUpdate,
    saveCustomEntry,
    confirmDeleteCustomEntry,
    removeNonCustomEntry,
    toggleWeaponOwnership,
    updateWeaponPriority,
  }
}
