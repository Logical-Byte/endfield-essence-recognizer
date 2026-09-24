/**
 * 基质规划器组合式函数。
 *
 * 改编自 ef-frontend-v1 的基质计算器逻辑，帮助用户找到刷取所需基质的最佳位置。
 */

import type { EnergyAlluviumInfo } from '@/types/staticData'
import { computed, onUnmounted, ref, type Ref, watch } from 'vue'
import { useCustomStats } from '@/composables/useCustomStats'
import { useProfiles } from '@/composables/useProfiles'
import { useStaticData } from '@/utils/gameData/staticData'
import { findCustomStat, getGemTagName, isCustomStatId } from '@/utils/gameData/weapon'
import { safeLoadJson, safeRemoveJson, safeSetJson } from '@/utils/safeStorage'

let _nextId = 1

export interface PlannerEssenceStat {
  /** 唯一标识符，用于 v-for key 和稳定引用 */
  id: number
  isCustom: boolean
  weaponId: string | null
  attribute: string | null
  secondary: string | null
  skill: string | null
}

export interface BattleChoice {
  battleId: string
  battleName: string
  selectedAttribute: string[]
  selectedSecondary: string | null
  selectedSkill: string | null
  matchedSelectedIndices: number[]
  matchedWeaponIds: string[]
}

export interface EnergyAlluvium {
  battleId: string
  battleName: string
  imageUrl?: string
  secondaryStats: string[]
  skillStats: string[]
}

interface PlannerWeaponStats {
  weaponId: string
  attribute: string
  secondary: string
  skill: string
}

/** 淤积点名称前缀，显示时裁掉 */
const ALLUVIUM_PREFIX = '重度能量淤积点·'

/**
 * 将完整淤积点名称裁剪为短显示名。
 * 如 "重度能量淤积点·枢纽区" → "枢纽区"。
 */
export function getDisplayName(battleName: string): string {
  return battleName.startsWith(ALLUVIUM_PREFIX)
    ? battleName.slice(ALLUVIUM_PREFIX.length)
    : battleName
}

// 所有属性词条
const allAttributeStats = ['敏捷提升', '力量提升', '意志提升', '智识提升', '主能力提升']
const allAttributeCombinations = combinations(allAttributeStats, 3)

// 所有副属性词条
const allSecondaryStats = [
  '攻击提升',
  '生命提升',
  '物理伤害提升',
  '灼热伤害提升',
  '电磁伤害提升',
  '寒冷伤害提升',
  '自然伤害提升',
  '暴击率提升',
  '源石技艺提升',
  '终结技充能效率提升',
  '法术伤害提升',
  '治疗效率提升',
]

// 所有技能词条
const allSkillStats = [
  '强攻',
  '压制',
  '追袭',
  '粉碎',
  '昂扬',
  '巧技',
  '残暴',
  '附术',
  '医疗',
  '切骨',
  '迸发',
  '夜幕',
  '流转',
  '效益',
]

function combinations<T>(arr: T[], size: number): T[][] {
  if (size === 0) return [[]]
  if (arr.length < size) return []
  const result: T[][] = []
  for (let index = 0; index <= arr.length - size; index++) {
    const rest = arr.slice(index + 1)
    for (const combo of combinations(rest, size - 1)) {
      result.push([arr[index]!, ...combo])
    }
  }
  return result
}

function getStatDisplayName(statId: string | null): string {
  if (!statId) return ''
  return getGemTagName(statId)
}

/** 自定义基质名称缓存，由页面层注入 */
function clearAllStats(
  requiredEssenceStats: Ref<PlannerEssenceStat[]>,
  lastSelectedWeaponId: Ref<string | null>,
) {
  requiredEssenceStats.value = []
  lastSelectedWeaponId.value = null
}

/** 将单个需求词条与战斗可用词条进行匹配。 */
function requirementMatchesBattle(
  stat: PlannerEssenceStat,
  selectedAttributes: string[],
  selectedSecondary: string | null,
  selectedSkill: string | null,
  battleSecondaryStats: string[],
  battleSkillStats: string[],
): boolean {
  if (!stat.attribute || !stat.secondary || !stat.skill) return false
  if (!selectedAttributes.includes(stat.attribute)) return false
  if (selectedSecondary !== null) {
    return stat.secondary === selectedSecondary && battleSkillStats.includes(stat.skill)
  }
  if (selectedSkill !== null) {
    return battleSecondaryStats.includes(stat.secondary) && stat.skill === selectedSkill
  }
  return false
}

/** 查找匹配战斗词条组合的所有武器。 */
function findMatchingWeapons(
  weaponStats: PlannerWeaponStats[],
  selectedAttributes: string[],
  battleSecondaryStats: string[],
  battleSkillStats: string[],
  selectedSecondary: string | null,
  selectedSkill: string | null,
): string[] {
  const matched: string[] = []
  for (const weapon of weaponStats) {
    if (!selectedAttributes.includes(weapon.attribute)) continue
    const secOk =
      selectedSecondary !== null
        ? weapon.secondary === selectedSecondary
        : battleSecondaryStats.includes(weapon.secondary)
    const skillOk =
      selectedSkill !== null
        ? weapon.skill === selectedSkill
        : battleSkillStats.includes(weapon.skill)
    if (secOk && skillOk) matched.push(weapon.weaponId)
  }
  return matched
}

export function useMatrixPlanner(obtainedWeaponIds?: Ref<Set<string>>) {
  const { weaponsMap, essencesMap, energyAlluviums: energyAlluviumsFromApi } = useStaticData()
  const { activeProfileName } = useProfiles()
  const { customStats } = useCustomStats()

  /** stat_id → 中文显示名映射（从 essencesMap 构建） */
  const statIdToNameMap = computed<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    for (const [id, essence] of essencesMap.value.entries()) {
      map[id] = essence.name
    }
    return map
  })

  /**
   * 将词条内部 ID（如 "gat_passive_attr_atk"）解析为中文显示名。
   * 查 essencesMap 映射表，未命中则返回原键。
   */
  function resolveStatKeyToDisplayName(key: string): string {
    return statIdToNameMap.value[key] ?? key
  }

  /** 能量淤积点数据（刷取位置），从 API 获取并转换为中文显示名 */
  const energyAlluviums = computed<Record<string, EnergyAlluvium>>(() => {
    return Object.fromEntries(
      energyAlluviumsFromApi.value.map((item: EnergyAlluviumInfo) => {
        const converted: EnergyAlluvium = {
          battleId: item.battleId,
          battleName: item.battleName,
          imageUrl: item.imageUrl,
          secondaryStats: item.secondaryStats.map((key) => resolveStatKeyToDisplayName(key)),
          skillStats: item.skillStats.map((key) => resolveStatKeyToDisplayName(key)),
        }
        return [converted.battleName, converted]
      }),
    )
  })

  // 缓存 key 绑定到账号，避免跨账号数据污染
  const statsKey = computed(() => `matrixPlannerStats:${activeProfileName.value}`)

  // 规划计算会反复按词条匹配武器，先把武器 ID 转成显示词条，避免在每个方案里重复转换。
  const weaponPlannerStats = computed<PlannerWeaponStats[]>(() => {
    const rows: PlannerWeaponStats[] = []
    for (const [weaponId, weapon] of weaponsMap.value.entries()) {
      const attribute = getStatDisplayName(weapon.attributeStatId)
      const secondary = getStatDisplayName(weapon.secondaryStatId)
      const skill = getStatDisplayName(weapon.skillStatId)
      if (!attribute || !secondary || !skill) continue
      rows.push({ weaponId, attribute, secondary, skill })
    }
    return rows
  })

  const requiredEssenceStats = ref<PlannerEssenceStat[]>([])
  const lastSelectedWeaponId = ref<string | null>(null)
  let saveStatsTimer: number | undefined

  // 账号切换时重新加载缓存
  watch(
    activeProfileName,
    () => {
      const initialStats = safeLoadJson<PlannerEssenceStat[]>(statsKey.value, [])
      _nextId = Math.max(
        _nextId,
        Math.max(
          0,
          ...initialStats
            .map((stat) => stat.id)
            .filter((id): id is number => typeof id === 'number'),
        ) + 1,
      )
      requiredEssenceStats.value = initialStats
    },
    { immediate: true },
  )

  // 监听变化并保存到localStorage
  watch(
    requiredEssenceStats,
    (newStats) => {
      window.clearTimeout(saveStatsTimer)
      saveStatsTimer = window.setTimeout(() => {
        if (newStats.length > 0) {
          safeSetJson(statsKey.value, newStats)
        } else {
          safeRemoveJson(statsKey.value)
        }
      }, 300)
    },
    { deep: true },
  )

  onUnmounted(() => {
    window.clearTimeout(saveStatsTimer)
  })

  function addStatFromWeapon(weaponId: string) {
    const weapon = weaponsMap.value.get(weaponId)
    if (!weapon) return

    // 记录最后选择的武器
    lastSelectedWeaponId.value = weaponId

    // 检查是否已添加 — 切换关闭
    const existing = requiredEssenceStats.value.findIndex(
      (s) => !s.isCustom && s.weaponId === weaponId,
    )
    if (existing !== -1) {
      requiredEssenceStats.value.splice(existing, 1)
      return
    }
    // 存储显示名（而非内部 ID），确保与 allAttributeStats 等匹配一致
    requiredEssenceStats.value.push({
      id: _nextId++,
      isCustom: false,
      weaponId,
      attribute: getStatDisplayName(weapon.attributeStatId),
      secondary: getStatDisplayName(weapon.secondaryStatId),
      skill: getStatDisplayName(weapon.skillStatId),
    })
  }

  /** 从自定义基质预设添加/移除需求词条 */
  function addStatFromCustomPreset(
    syntheticId: string,
    attribute: string,
    secondary: string,
    skill: string,
  ) {
    lastSelectedWeaponId.value = syntheticId

    // 检查是否已添加 — 切换关闭
    const existing = requiredEssenceStats.value.findIndex(
      (s) => !s.isCustom && s.weaponId === syntheticId,
    )
    if (existing !== -1) {
      requiredEssenceStats.value.splice(existing, 1)
      return
    }

    requiredEssenceStats.value.push({
      id: _nextId++,
      isCustom: false,
      weaponId: syntheticId,
      attribute,
      secondary,
      skill,
    })
  }

  function addCustomStat() {
    requiredEssenceStats.value.push({
      id: _nextId++,
      isCustom: true,
      weaponId: null,
      attribute: null,
      secondary: null,
      skill: null,
    })
  }

  function removeStat(index: number) {
    requiredEssenceStats.value.splice(index, 1)
  }

  function moveStatUp(index: number) {
    if (index === 0) return
    const item = requiredEssenceStats.value.splice(index, 1)[0]!
    requiredEssenceStats.value.splice(index - 1, 0, item)
  }

  function moveStatDown(index: number) {
    if (index === requiredEssenceStats.value.length - 1) return
    const item = requiredEssenceStats.value.splice(index, 1)[0]!
    requiredEssenceStats.value.splice(index + 1, 0, item)
  }

  function getEssenceStatDescription(stat: PlannerEssenceStat): string {
    if (stat.isCustom) return '自定义'
    if (stat.weaponId) {
      // 识别自定义基质预设的合成 ID（兼容新旧格式）
      if (isCustomStatId(stat.weaponId)) {
        const found = findCustomStat(stat.weaponId, customStats.value)
        return found?.stat.name || `自定义基质 ${found ? found.index + 1 : ''}`
      }
      const weapon = weaponsMap.value.get(stat.weaponId)
      return weapon ? weapon.name : stat.weaponId
    }
    return '未知'
  }

  /** 将匹配的自定义基质合成 ID 追加到 matchedWeaponIds 中 */
  function _appendCustomStatMatches(
    matchedWeaponIds: string[],
    selectedAttribute: string[],
    selectedSecondary: string | null,
    selectedSkill: string | null,
    battleSecondaryStats: string[],
    battleSkillStats: string[],
  ) {
    for (const stat of requiredEssenceStats.value) {
      if (!stat.weaponId || !isCustomStatId(stat.weaponId)) continue
      if (
        requirementMatchesBattle(
          stat,
          selectedAttribute,
          selectedSecondary,
          selectedSkill,
          battleSecondaryStats,
          battleSkillStats,
        )
      ) {
        matchedWeaponIds.push(stat.weaponId)
      }
    }
  }

  function buildChoiceForSecondary(
    battleId: string,
    battleName: string,
    selectedAttribute: string[],
    selectedSecondary: string,
    battleSkillStats: string[],
  ): BattleChoice | undefined {
    const matchedSelectedIndices: number[] = []
    for (const [index, stat] of requiredEssenceStats.value.entries()) {
      if (
        requirementMatchesBattle(
          stat,
          selectedAttribute,
          selectedSecondary,
          null,
          [],
          battleSkillStats,
        )
      ) {
        matchedSelectedIndices.push(index)
      }
    }
    if (matchedSelectedIndices.length === 0) return undefined
    const matchedWeaponIds = findMatchingWeapons(
      weaponPlannerStats.value,
      selectedAttribute,
      [],
      battleSkillStats,
      selectedSecondary,
      null,
    )
    _appendCustomStatMatches(
      matchedWeaponIds,
      selectedAttribute,
      selectedSecondary,
      null,
      [],
      battleSkillStats,
    )
    return {
      battleId,
      battleName,
      selectedAttribute,
      selectedSecondary,
      selectedSkill: null,
      matchedSelectedIndices,
      matchedWeaponIds,
    }
  }

  function buildChoiceForSkill(
    battleId: string,
    battleName: string,
    selectedAttribute: string[],
    selectedSkill: string,
    battleSecondaryStats: string[],
  ): BattleChoice | undefined {
    const matchedSelectedIndices: number[] = []
    for (const [index, stat] of requiredEssenceStats.value.entries()) {
      if (
        requirementMatchesBattle(
          stat,
          selectedAttribute,
          null,
          selectedSkill,
          battleSecondaryStats,
          [],
        )
      ) {
        matchedSelectedIndices.push(index)
      }
    }
    if (matchedSelectedIndices.length === 0) return undefined
    const matchedWeaponIds = findMatchingWeapons(
      weaponPlannerStats.value,
      selectedAttribute,
      battleSecondaryStats,
      [],
      null,
      selectedSkill,
    )
    _appendCustomStatMatches(
      matchedWeaponIds,
      selectedAttribute,
      null,
      selectedSkill,
      battleSecondaryStats,
      [],
    )
    return {
      battleId,
      battleName,
      selectedAttribute,
      selectedSecondary: null,
      selectedSkill,
      matchedSelectedIndices,
      matchedWeaponIds,
    }
  }

  const battleChoices = ref<BattleChoice[]>([])

  /**
   * 重新计算所有可能的刷取方案。
   * 遍历每个能量淤积点，对每个地点生成所有 3 属性组合（共 C(5,3)=10 种），
   * 再分别与该地点的附加属性、技能属性配对，筛选出至少满足一项需求的方案。
   */
  function _recomputeChoices() {
    const result: BattleChoice[] = []
    for (const { battleId, battleName, secondaryStats, skillStats } of Object.values(
      energyAlluviums.value,
    )) {
      for (const selectedAttribute of allAttributeCombinations) {
        for (const selectedSecondary of secondaryStats) {
          const choice = buildChoiceForSecondary(
            battleId,
            battleName,
            selectedAttribute,
            selectedSecondary,
            skillStats,
          )
          if (choice) result.push(choice)
        }
        for (const selectedSkill of skillStats) {
          const choice = buildChoiceForSkill(
            battleId,
            battleName,
            selectedAttribute,
            selectedSkill,
            secondaryStats,
          )
          if (choice) result.push(choice)
        }
      }
    }
    battleChoices.value = result
  }

  watch(requiredEssenceStats, () => _recomputeChoices(), { deep: true, immediate: true })

  // 淤积点数据是异步到达的：若需求在数据就绪前建立（或从缓存恢复），
  // 上面的 watch 只在空数据上算过一遍，之后没有触发点，方案列表会永久为空。
  // 数据到达时补算一次，保证首屏方案可用。
  watch(energyAlluviums, () => _recomputeChoices())

  /** 按优先级排序后的所有有效方案：满足需求数 > 匹配已选武器数 > 未获得武器数 > 匹配武器总数 */
  const _sortedChoices = computed(() => {
    const filtered = battleChoices.value.filter(
      ({ matchedSelectedIndices }) => matchedSelectedIndices.length > 0,
    )

    const selectedWeaponIds = new Set(
      requiredEssenceStats.value
        .filter((stat) => !stat.isCustom && stat.weaponId)
        .map((stat) => stat.weaponId!),
    )

    const obtainedIds = obtainedWeaponIds?.value ?? new Set<string>()

    return filtered.toSorted((a, b) => {
      // 优先：满足更多需求
      if (b.matchedSelectedIndices.length !== a.matchedSelectedIndices.length) {
        return b.matchedSelectedIndices.length - a.matchedSelectedIndices.length
      }

      // 其次：匹配更多已选择的武器
      const aMatchedSelected = a.matchedWeaponIds.filter((id) => selectedWeaponIds.has(id)).length
      const bMatchedSelected = b.matchedWeaponIds.filter((id) => selectedWeaponIds.has(id)).length
      if (aMatchedSelected !== bMatchedSelected) {
        return bMatchedSelected - aMatchedSelected
      }

      // 再次：匹配武器中未获得的数量更多
      const aUnobtained = a.matchedWeaponIds.filter((id) => !obtainedIds.has(id)).length
      const bUnobtained = b.matchedWeaponIds.filter((id) => !obtainedIds.has(id)).length
      if (aUnobtained !== bUnobtained) {
        return bUnobtained - aUnobtained
      }

      // 最后：匹配武器总数
      return b.matchedWeaponIds.length - a.matchedWeaponIds.length
    })
  })

  /** 最优的前 5 个方案（使用预刻券模式） */
  const bestChoices = computed(() => _sortedChoices.value.slice(0, 5))

  /** 所有有效方案（不使用预刻券模式） */
  const allChoices = computed(() => _sortedChoices.value)

  return {
    requiredEssenceStats,
    lastSelectedWeaponId,
    allAttributeStats,
    allSecondaryStats,
    allSkillStats,
    energyAlluviums,
    addStatFromWeapon,
    addStatFromCustomPreset,
    addCustomStat,
    removeStat,
    moveStatUp,
    moveStatDown,
    getEssenceStatDescription,
    getStatDisplayName,
    battleChoices,
    bestChoices,
    allChoices,
    clearAllStats: () => clearAllStats(requiredEssenceStats, lastSelectedWeaponId),
  }
}
