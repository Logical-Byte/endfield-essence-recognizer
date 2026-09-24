/**
 * 武器状态查询组合式函数。
 *
 * 提供武器的各种状态查询方法，包括拥有状态、满级判断、优先级计算等。
 */

import type { TreasureMatrixEntry } from '@/composables/useProfiles'
import { computed } from 'vue'
import { useProfiles } from '@/composables/useProfiles'
import { useStaticData } from '@/utils/gameData/staticData'
import { buildStatKey, isCustomStatId } from '@/utils/gameData/weapon'

/** 各词条的最大等级，与后端 schemas/profile.py 的 le 约束保持一致 */
export const AFFIX_MAX_LEVEL = [6, 6, 3] as const

export function useWeaponStats() {
  const { activeProfile, treasureMatrix } = useProfiles()
  const { weaponsMap } = useStaticData()

  // 核心索引：weapon_id -> TreasureMatrixEntry
  const matrixEntryByWeaponId = computed(
    () => new Map(treasureMatrix.value.map((entry) => [entry.weapon_id, entry])),
  )

  // 已拥有的武器 ID 集合
  const ownedWeaponIds = computed(() => new Set(matrixEntryByWeaponId.value.keys()))

  /**
   * 属性组合 -> 武器 ID 列表的索引。
   *
   * 「查找同属性武器」会在每个武器格子的渲染里被调用多次，逐次线性扫描
   * weaponsMap 会让总览页退化成 O(n²)；这里预先建索引，把查找降到 O(1)。
   */
  const weaponIdsByStatKey = computed(() => {
    const index = new Map<string, string[]>()
    for (const [id, weapon] of weaponsMap.value.entries()) {
      const key = buildStatKey(weapon.attributeStatId, weapon.secondaryStatId, weapon.skillStatId)
      const bucket = index.get(key)
      if (bucket) {
        bucket.push(id)
      } else {
        index.set(key, [id])
      }
    }
    return index
  })

  /**
   * 判断武器是否已拥有
   */
  function isWeaponOwned(weaponId: string): boolean {
    return ownedWeaponIds.value.has(weaponId)
  }

  /**
   * 判断武器是否满级（6/6/3）
   */
  function isWeaponMaxed(weaponId: string): boolean {
    const entry = matrixEntryByWeaponId.value.get(weaponId)
    return (
      entry !== undefined &&
      entry.affix1_level === AFFIX_MAX_LEVEL[0] &&
      entry.affix2_level === AFFIX_MAX_LEVEL[1] &&
      entry.affix3_level === AFFIX_MAX_LEVEL[2]
    )
  }

  /**
   * 判断是否为自定义基质条目
   */
  function isCustomEntry(weaponId: string | null): boolean {
    return isCustomStatId(weaponId)
  }

  /**
   * 获取用户手动设置的优先级（0 表示未设置）
   */
  function getUserPriority(weaponId: string): number {
    const profilePriority = activeProfile.value.weapon_priorities?.[weaponId]
    if (profilePriority && profilePriority > 0) return profilePriority
    const entry = matrixEntryByWeaponId.value.get(weaponId)
    return entry?.priority || 0
  }

  /**
   * 获取武器的有效优先级（未设置时使用稀有度）
   * 自定义条目默认优先级为 6（等同于 6★）
   */
  function getWeaponPriority(weaponId: string): number {
    const userP = getUserPriority(weaponId)
    if (userP > 0) return userP
    // 自定义条目默认优先级为 6
    if (isCustomEntry(weaponId)) return 6
    const weapon = weaponsMap.value.get(weaponId)
    return weapon ? weapon.rarity : 0
  }

  /**
   * 获取交换时的有效优先级
   */
  function getEffectivePriorityForSwap(weaponId: string, entry?: TreasureMatrixEntry): number {
    const userPriority = getUserPriority(weaponId) || entry?.priority || 0
    if (userPriority > 0) return userPriority
    // 与 getWeaponPriority 保持一致：自定义条目按 6★ 处理，
    // 否则交换时会被当成优先级 0，凭空低于任何一把普通武器。
    if (isCustomEntry(weaponId)) return 6
    const weapon = weaponsMap.value.get(weaponId)
    return weapon ? weapon.rarity : 0
  }

  /**
   * 获取同类武器（相同属性组合）
   * 自定义条目没有真实武器数据，返回空数组
   */
  function getSameStatWeapons(weaponId: string): string[] {
    if (isCustomEntry(weaponId)) return []
    const weapon = weaponsMap.value.get(weaponId)
    if (!weapon) return []
    const key = buildStatKey(weapon.attributeStatId, weapon.secondaryStatId, weapon.skillStatId)
    const bucket = weaponIdsByStatKey.value.get(key)
    if (!bucket) return []
    return bucket.filter((id) => id !== weaponId)
  }

  /**
   * 「可切换」及「切换目标已满级」的预计算集合。
   *
   * 总览页每个武器格子会重复判断这两个状态（v-if、样式类各一次），
   * 而模板里的函数调用不会被 Vue 缓存。放进 computed 后整页只算一次，
   * 依赖变化时才重算。
   */
  const switchableSets = computed(() => {
    const switchable = new Set<string>()
    const targetMaxed = new Set<string>()
    for (const weaponId of weaponsMap.value.keys()) {
      const myPriority = getWeaponPriority(weaponId)
      let canSwitch = false
      let hasMaxedTarget = false
      for (const id of getSameStatWeapons(weaponId)) {
        if (!isWeaponOwned(id) || getWeaponPriority(id) < myPriority) continue
        canSwitch = true
        if (isWeaponMaxed(id)) {
          hasMaxedTarget = true
          break
        }
      }
      if (canSwitch) switchable.add(weaponId)
      if (hasMaxedTarget) targetMaxed.add(weaponId)
    }
    return { switchable, targetMaxed }
  })

  /**
   * 判断武器是否"可切换"：存在同属性、优先级不低于自己、且已拥有的武器。
   *
   * 用 >= 而非 >：两把同属性同稀有度的武器都拥有时互相提示，
   * 正是需要让用户注意到的重复情况。
   */
  function isSwitchable(weaponId: string): boolean {
    return switchableSets.value.switchable.has(weaponId)
  }

  /**
   * 获取可切换的目标武器是否满级（用于灰色呼吸动画）
   */
  function isSwitchTargetMaxed(weaponId: string): boolean {
    return switchableSets.value.targetMaxed.has(weaponId)
  }

  /**
   * 获取武器的基质等级文本
   */
  function getMatrixLevelText(weaponId: string): string {
    const entry = matrixEntryByWeaponId.value.get(weaponId)
    if (!entry) return '未配置'
    return `+${entry.affix1_level} / +${entry.affix2_level} / +${entry.affix3_level}`
  }

  return {
    // 状态
    matrixEntryByWeaponId,
    ownedWeaponIds,
    treasureMatrix,

    // 查询方法
    isWeaponOwned,
    isWeaponMaxed,
    isCustomEntry,
    getUserPriority,
    getWeaponPriority,
    getEffectivePriorityForSwap,
    getSameStatWeapons,
    isSwitchable,
    isSwitchTargetMaxed,
    getMatrixLevelText,
  }
}
