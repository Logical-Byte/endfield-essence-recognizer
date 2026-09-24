/**
 * 重合检测组合式函数。
 *
 * 检测自定义基质与内置武器的重合并处理。
 */

import type { TreasureMatrixEntry } from '@/composables/useProfiles'
import type { CustomStat } from '@/utils/gameData/weapon'
import { ref } from 'vue'
import { useCustomStats } from '@/composables/useCustomStats'
import { useProfiles } from '@/composables/useProfiles'
import { useStaticData } from '@/utils/gameData/staticData'
import {
  fallbackCustomStatName,
  findCustomStat,
  getGemTagName,
  toCustomStatId,
} from '@/utils/gameData/weapon'

export interface OverlapItem {
  /** 自定义基质的稳定 ID（不随增删变化） */
  customStatId: string
  customName: string
  customWeaponId: string
  /** 与该自定义基质词条完全相同的内置武器，可能有多把 */
  matchedWeaponIds: string[]
  matchedWeaponNames: string[]
  action: 'ignore' | 'suppress' | 'switch' | 'delete'
  /** action 为 switch 时，切换到的目标武器 ID */
  switchTargetId: string
}

/** 重合检测的物品列表（模块级单例，所有调用方共享同一份状态） */
const overlapItems = ref<OverlapItem[]>([])

/** 重合检测弹窗是否显示 */
const overlapDialog = ref(false)

/** 重合检测的等级比较结果（按 overlapItems 索引缓存） */
const overlapCompareResults = ref<Map<number, number>>(new Map())

/** 比较结果是否已就绪：未就绪时禁用「一键选择」，避免按空结果全选"忽略" */
const overlapCompareReady = ref(false)

/** 仅供测试使用：重置模块级单例状态 */
export function __resetOverlapStateForTests() {
  overlapItems.value = []
  overlapDialog.value = false
  overlapCompareResults.value = new Map()
  overlapCompareReady.value = false
}

export function useOverlapDetection() {
  const { updateTreasureMatrix } = useProfiles()
  const { weaponsMap, essencesMap } = useStaticData()
  const { postCustomStatsUpdate } = useCustomStats()

  /**
   * 检查自定义基质与内置武器的词条重合
   * 匹配规则：三个槽位完全相等（含 null 对 null）
   * 检查范围：所有 config 中配置的自定义基质，无论是否在 profiles 中拥有
   *
   * 同一个自定义基质可能同时匹配多把武器（同属性组合的武器在游戏里很常见），
   * 这些匹配会聚合进同一条记录 —— 每个基质至多产生一条待决策项，
   * 使"移除/切换"这类针对基质本身的操作不会被重复执行。
   *
   * 「不再提示」标记只约束自动检测（进入宝藏基质页面时弹出）：手动点击
   * 「检查自定义基质重合」时传 `includeSuppressed: true`，已标记的条目
   * 仍然显示，否则用户一旦误选就再也无法通过界面找回。
   */
  function checkCustomOverlap(
    customStats: CustomStat[],
    matrixEntryByWeaponId: ReadonlyMap<string, TreasureMatrixEntry>,
    options: { includeSuppressed?: boolean } = {},
  ) {
    const { includeSuppressed = false } = options
    const items: OverlapItem[] = []
    for (const [i, stat] of customStats.entries()) {
      if (!stat) continue
      // 跳过已勾选"不再提示"的（仅自动检测遵守该标记，手动检测带上它们）
      if (!includeSuppressed && stat.no_prompt_switch) continue
      // 跳过属性全为空的条目（已被切换清空）
      if (!stat.attribute && !stat.secondary && !stat.skill) continue

      const matchedWeaponIds: string[] = []
      const matchedWeaponNames: string[] = []
      for (const [weaponId, weapon] of weaponsMap.value.entries()) {
        if (
          weapon.attributeStatId === stat.attribute &&
          weapon.secondaryStatId === stat.secondary &&
          weapon.skillStatId === stat.skill
        ) {
          matchedWeaponIds.push(weaponId)
          matchedWeaponNames.push(weapon.name)
        }
      }
      if (matchedWeaponIds.length === 0) continue

      items.push({
        customStatId: stat.id,
        customName: stat.name || fallbackCustomStatName(i),
        customWeaponId: toCustomStatId(stat),
        matchedWeaponIds,
        matchedWeaponNames,
        action: 'ignore',
        switchTargetId: matchedWeaponIds[0]!,
      })
    }
    if (items.length === 0) return
    overlapItems.value = items
    overlapCompareResults.value = new Map()
    overlapCompareReady.value = false
    overlapDialog.value = true
    return fetchOverlapCompareResults({
      matrixEntryByWeaponId,
      customStats,
    })
  }

  /**
   * 从后端批量获取重合检测的等级比较结果
   *
   * 使用用户在设置中选择的比较方式，与扫描时的"留大弃小"判定保持一致。
   */
  async function fetchOverlapCompareResults(params: {
    matrixEntryByWeaponId: ReadonlyMap<string, TreasureMatrixEntry>
    customStats: CustomStat[]
  }) {
    const { matrixEntryByWeaponId, customStats } = params
    if (overlapItems.value.length === 0) return

    try {
      const mode = await fetchKeepBestMode()
      const res = await fetch('/api/profiles/compare_levels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          items: overlapItems.value.map((item) => {
            const customEntry = matrixEntryByWeaponId.get(item.customWeaponId)
            const matchedEntry = matrixEntryByWeaponId.get(item.switchTargetId)
            return {
              current_levels: [
                customEntry?.affix1_level ?? 0,
                customEntry?.affix2_level ?? 0,
                customEntry?.affix3_level ?? 0,
              ],
              existing_levels: [
                matchedEntry?.affix1_level ?? 0,
                matchedEntry?.affix2_level ?? 0,
                matchedEntry?.affix3_level ?? 0,
              ],
              stat_types: resolveStatTypes(item.customWeaponId, customStats),
            }
          }),
        }),
      })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      const data = await res.json()
      const results = new Map<number, number>()
      for (let i = 0; i < overlapItems.value.length; i++) {
        results.set(i, data.results?.[i] ?? 0)
      }
      overlapCompareResults.value = results
      overlapCompareReady.value = true
    } catch (error) {
      // 保持 overlapCompareReady 为 false：「一键选择」会禁用，
      // 用户仍可手动决策，但不会拿到一份看似有效的全零结果。
      throw new Error(
        `获取等级比较结果失败: ${error instanceof Error ? error.message : String(error)}`,
      )
    }
  }

  /** 读取用户配置的"留大弃小"比较方式，失败时回退为后端默认值 */
  async function fetchKeepBestMode(): Promise<string> {
    try {
      const res = await fetch('/api/config')
      if (!res.ok) return 'sequential'
      const config = await res.json()
      return config.same_type_keep_best_mode || 'sequential'
    } catch {
      return 'sequential'
    }
  }

  /**
   * 解析武器 ID 对应的三个槽位词条类型
   * 返回 ["ATTRIBUTE", "SECONDARY", "SKILL"] 或对应的 null
   */
  function resolveStatTypes(weaponId: string, customStats: CustomStat[]): (string | null)[] {
    const found = findCustomStat(weaponId, customStats)
    if (found) {
      const { stat } = found
      return [
        stat.attribute ? (essencesMap.value.get(stat.attribute)?.type ?? null) : null,
        stat.secondary ? (essencesMap.value.get(stat.secondary)?.type ?? null) : null,
        stat.skill ? (essencesMap.value.get(stat.skill)?.type ?? null) : null,
      ]
    }
    const weapon = weaponsMap.value.get(weaponId)
    return [
      weapon?.attributeStatId ? 'ATTRIBUTE' : null,
      weapon?.secondaryStatId ? 'SECONDARY' : null,
      weapon?.skillStatId ? 'SKILL' : null,
    ]
  }

  /**
   * 获取预计算的比较结果：1（自定义更优）/ 0（相等）/ -1（内置更优）
   */
  function getOverlapCompareResult(index: number): number {
    return overlapCompareResults.value.get(index) ?? 0
  }

  /**
   * 一键选择：根据比较结果自动选择动作
   *
   * 比较结果未就绪时不做任何事——按一份尚未填充的结果全选"忽略"，
   * 看起来和"逐条确认过"没有区别，属于最难察觉的那类错误建议。
   */
  function autoSelectOverlap() {
    if (!overlapCompareReady.value) return
    for (let i = 0; i < overlapItems.value.length; i++) {
      const item = overlapItems.value[i]
      if (!item) continue
      const cmp = overlapCompareResults.value.get(i) ?? 0
      if (cmp < 0) {
        item.action = 'delete' // 自定义更小 → 删除自定义
      } else if (cmp === 0) {
        item.action = 'ignore' // 相等 → 忽略
      } else {
        item.action = 'switch' // 自定义更大 → 切换到内置
      }
    }
  }

  /**
   * 获取重合检测中某个武器 ID 的属性词条文本（含等级）
   */
  function getOverlapTooltipText(
    weaponId: string,
    params: {
      matrixEntryByWeaponId: ReadonlyMap<string, TreasureMatrixEntry>
      customStats: CustomStat[]
    },
  ): string {
    const { matrixEntryByWeaponId, customStats } = params
    const entry = matrixEntryByWeaponId.get(weaponId)
    const levels: [number, number, number] = [
      entry?.affix1_level ?? 0,
      entry?.affix2_level ?? 0,
      entry?.affix3_level ?? 0,
    ]

    const found = findCustomStat(weaponId, customStats)
    let statIds: (string | null)[]
    if (found) {
      const { stat } = found
      statIds = [stat.attribute ?? null, stat.secondary ?? null, stat.skill ?? null]
    } else {
      const weapon = weaponsMap.value.get(weaponId)
      statIds = [
        weapon?.attributeStatId ?? null,
        weapon?.secondaryStatId ?? null,
        weapon?.skillStatId ?? null,
      ]
    }

    const parts: string[] = []
    for (let i = 0; i < 3; i++) {
      const sid = statIds[i]
      if (sid) {
        parts.push(`${getGemTagName(sid)} Lv.${levels[i]}`)
      }
    }
    return parts.join('、') || '无属性'
  }

  /**
   * 确认重合操作
   *
   * 所有决策都按稳定 ID 定位，删除自定义基质不会牵动其余条目的标识，
   * 因此既不需要重排索引，也不存在"标记打到隔壁条目上"的可能。
   */
  async function confirmOverlapActions(params: {
    customStats: CustomStat[]
    treasureMatrix: readonly TreasureMatrixEntry[]
    matrixEntryByWeaponId: ReadonlyMap<string, TreasureMatrixEntry>
  }) {
    const { customStats, matrixEntryByWeaponId, treasureMatrix } = params

    const idsToDelete = new Set<string>()
    const idsToSuppress = new Set<string>()
    for (const item of overlapItems.value) {
      if (item.action === 'switch' || item.action === 'delete') {
        idsToDelete.add(item.customStatId)
      } else if (item.action === 'suppress') {
        idsToSuppress.add(item.customStatId)
      }
    }

    if (idsToDelete.size === 0 && idsToSuppress.size === 0) {
      return { deletedIds: [], suppressedIds: [] }
    }

    // 构建新的 treasure_matrix：先移除被处理掉的自定义条目
    const removedWeaponIds = new Set(
      overlapItems.value
        .filter((i) => i.action === 'switch' || i.action === 'delete')
        .map((i) => i.customWeaponId),
    )
    const newTreasureMatrix = treasureMatrix.filter((e) => !removedWeaponIds.has(e.weapon_id))

    // 处理 switch：把等级、计算开关与优先级一并转移到目标武器上
    for (const item of overlapItems.value) {
      if (item.action !== 'switch') continue

      const entry = matrixEntryByWeaponId.get(item.customWeaponId)
      if (!entry) continue

      const targetId = item.switchTargetId
      const weapon = weaponsMap.value.get(targetId)
      const targetName =
        weapon?.name || item.matchedWeaponNames[item.matchedWeaponIds.indexOf(targetId)] || targetId
      const transferred: TreasureMatrixEntry = {
        weapon_id: targetId,
        weapon_name: targetName,
        affix1_level: entry.affix1_level,
        affix2_level: entry.affix2_level,
        affix3_level: entry.affix3_level,
        include_in_calculation: entry.include_in_calculation ?? true,
        // 优先级同属基质数据的一部分，漏带会让切换后的武器掉回稀有度默认值
        priority: entry.priority,
      }

      const existingIndex = newTreasureMatrix.findIndex((e) => e.weapon_id === targetId)
      if (existingIndex === -1) {
        newTreasureMatrix.push(transferred)
      } else {
        // 目标武器已有基质：保留其原有数据，切换只负责移除重复的自定义条目
        continue
      }
    }

    // 准备新的 config 数据（按 ID 过滤 / 标记，与下标无关）
    const tempStats = customStats
      .filter((stat) => !idsToDelete.has(stat.id))
      .map((stat) => (idsToSuppress.has(stat.id) ? { ...stat, no_prompt_switch: true } : stat))

    if (idsToDelete.size > 0) {
      await updateTreasureMatrix(newTreasureMatrix)
    }
    await postCustomStatsUpdate(tempStats)

    return {
      deletedIds: [...idsToDelete],
      suppressedIds: [...idsToSuppress],
    }
  }

  return {
    // 状态
    overlapItems,
    overlapDialog,
    overlapCompareResults,
    overlapCompareReady,

    // 检测方法
    checkCustomOverlap,
    fetchOverlapCompareResults,
    getOverlapCompareResult,
    autoSelectOverlap,
    getOverlapTooltipText,

    // 操作方法
    confirmOverlapActions,
  }
}
