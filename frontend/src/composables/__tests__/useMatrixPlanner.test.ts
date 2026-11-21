/**
 * 基质规划器的自定义淤积点测试。
 *
 * 自定义地点走的是与内置地点同一套规划逻辑，但基础属性只由用户勾选的池决定。
 * 这里固定住三件事：自定义地点参与方案计算、基础属性池生效、内置武器与自定义
 * 基质都能被自定义地点匹配到。
 */

import type { EnergyAlluviumInfo, EssenceInfo, WeaponInfo } from '@/types/staticData'
import type { CustomAlluvium } from '@/utils/gameData/alluvium'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { useCustomAlluviums } from '@/composables/useCustomAlluviums'
import { useCustomStats } from '@/composables/useCustomStats'
import { useMatrixPlanner } from '@/composables/useMatrixPlanner'
import { CUSTOM_ALLUVIUM_ID_PREFIX } from '@/utils/gameData/alluvium'
import { useStaticData } from '@/utils/gameData/staticData'

const ESSENCES: EssenceInfo[] = [
  { id: 'attr_agi', name: '敏捷提升', tagName: '敏捷提升', type: 'ATTRIBUTE' },
  { id: 'attr_str', name: '力量提升', tagName: '力量提升', type: 'ATTRIBUTE' },
  { id: 'attr_wil', name: '意志提升', tagName: '意志提升', type: 'ATTRIBUTE' },
  { id: 'attr_int', name: '智识提升', tagName: '智识提升', type: 'ATTRIBUTE' },
  { id: 'attr_main', name: '主能力提升', tagName: '主能力提升', type: 'ATTRIBUTE' },
  { id: 'sec_atk', name: '攻击提升', tagName: '攻击提升', type: 'SECONDARY' },
  { id: 'sec_hp', name: '生命提升', tagName: '生命提升', type: 'SECONDARY' },
  { id: 'skill_force', name: '强攻', tagName: '强攻', type: 'SKILL' },
  { id: 'skill_tactic', name: '压制', tagName: '压制', type: 'SKILL' },
]

const WEAPONS: WeaponInfo[] = [
  {
    id: 'wpn_builtin',
    name: '内置武器',
    iconUrl: '',
    rarity: 6,
    attributeStatId: 'attr_agi',
    secondaryStatId: 'sec_atk',
    skillStatId: 'skill_force',
  },
]

/** 安装可用静态数据（技能/附加词条需能被解析成显示名） */
function installStaticData(alluviums: EnergyAlluviumInfo[] = []) {
  const state = useStaticData()
  state.essencesMap.value = new Map(ESSENCES.map((essence) => [essence.id, essence]))
  state.weaponsMap.value = new Map(WEAPONS.map((weapon) => [weapon.id, weapon]))
  state.energyAlluviums.value = alluviums
}

/** 安装自定义淤积点 */
function installCustomAlluviums(entries: CustomAlluvium[]) {
  const { customAlluviums } = useCustomAlluviums()
  customAlluviums.value = entries
}

beforeEach(() => {
  // useMatrixPlanner 用 localStorage 缓存需求列表、用 window 的定时器做防抖，
  // node 测试环境两者都不存在，这里补齐最小实现。
  vi.stubGlobal('localStorage', {
    getItem: () => null,
    setItem: () => undefined,
    removeItem: () => undefined,
  })
  vi.stubGlobal('window', globalThis)
  // 组合式函数在组件外调用时 onUnmounted 会打 Vue 警告，与本文件的断言无关
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  installStaticData()
  installCustomAlluviums([])
  useCustomStats().customStats.value = []
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('自定义淤积点参与方案计算', () => {
  it('只在勾选的附加 / 技能池里生成方案', async () => {
    installCustomAlluviums([
      {
        id: 'a1',
        name: '新版本淤积点',
        attribute_stats: ['attr_agi', 'attr_str', 'attr_wil'],
        secondary_stats: ['sec_atk', 'sec_hp'],
        skill_stats: ['skill_force', 'skill_tactic'],
      },
    ])
    const planner = useMatrixPlanner()
    planner.addStatFromWeapon('wpn_builtin')
    await nextTick()

    const choices = planner.allChoices.value
    // 需求是「敏捷 / 攻击 / 强攻」：只有命中它的附加、技能各一条方案
    expect(choices).toHaveLength(2)
    for (const choice of choices) {
      expect(choice.battleId).toBe(`${CUSTOM_ALLUVIUM_ID_PREFIX}a1`)
      expect(choice.battleName).toBe('新版本淤积点')
      expect(choice.selectedAttribute).toEqual(['敏捷提升', '力量提升', '意志提升'])
    }

    const bySecondary = choices.find((choice) => choice.selectedSecondary === '攻击提升')
    expect(bySecondary?.matchedWeaponIds).toContain('wpn_builtin')
    const bySkill = choices.find((choice) => choice.selectedSkill === '强攻')
    expect(bySkill?.matchedWeaponIds).toContain('wpn_builtin')
  })

  it('基础属性池不含需求的属性时，该地点不出方案', async () => {
    installCustomAlluviums([
      {
        id: 'a1',
        name: '只出敏捷的地点',
        attribute_stats: ['attr_agi', 'attr_str', 'attr_wil'],
        secondary_stats: ['sec_atk'],
        skill_stats: ['skill_force'],
      },
    ])
    const planner = useMatrixPlanner()
    // 需求的基础属性是智识提升，与地点的池没有交集
    planner.addStatFromCustomPreset('custom:x', '智识提升', '攻击提升', '强攻')
    await nextTick()

    expect(planner.allChoices.value).toEqual([])
  })

  it('基础属性池留空时按全部基础属性计算', async () => {
    installCustomAlluviums([
      {
        id: 'a1',
        name: '未限制基础属性的地点',
        attribute_stats: [],
        secondary_stats: ['sec_atk'],
        skill_stats: ['skill_force'],
      },
    ])
    const planner = useMatrixPlanner()
    planner.addStatFromCustomPreset('custom:x', '智识提升', '攻击提升', '强攻')
    await nextTick()

    const choices = planner.allChoices.value
    expect(choices.length).toBeGreaterThan(0)
    // 5 项取 3 的组合里，包含智识提升的共 C(4,2)=6 种
    const attributeCombos = new Set(choices.map((choice) => choice.selectedAttribute.join('|')))
    expect(attributeCombos.size).toBe(6)
    for (const choice of choices) {
      expect(choice.selectedAttribute).toContain('智识提升')
    }
  })

  it('自定义基质（宝藏基质）也能被自定义地点匹配', async () => {
    installCustomAlluviums([
      {
        id: 'a1',
        name: '新版本淤积点',
        attribute_stats: ['attr_agi', 'attr_str', 'attr_wil'],
        secondary_stats: ['sec_atk'],
        skill_stats: ['skill_force'],
      },
    ])
    useCustomStats().customStats.value = [
      {
        id: 's1',
        name: '自定义基质',
        attribute: 'attr_agi',
        secondary: 'sec_atk',
        skill: 'skill_force',
      },
    ]
    const planner = useMatrixPlanner()
    planner.addStatFromCustomPreset('custom:s1', '敏捷提升', '攻击提升', '强攻')
    await nextTick()

    const choices = planner.allChoices.value
    expect(choices.length).toBeGreaterThan(0)
    for (const choice of choices) {
      expect(choice.matchedWeaponIds).toContain('custom:s1')
    }
  })
})

describe('内置地点行为不变', () => {
  it('内置地点仍按 5 项基础属性的全部组合出方案', async () => {
    installStaticData([
      {
        battleId: 'world_energy_point_group01',
        battleName: '重度能量淤积点·枢纽区',
        secondaryStats: ['sec_atk'],
        skillStats: ['skill_force'],
      },
    ])
    const planner = useMatrixPlanner()
    planner.addStatFromCustomPreset('custom:x', '智识提升', '攻击提升', '强攻')
    await nextTick()

    const choices = planner.allChoices.value
    expect(choices.length).toBe(12)
    for (const choice of choices) {
      expect(choice.battleId).toBe('world_energy_point_group01')
    }
    const attributeCombos = new Set(choices.map((choice) => choice.selectedAttribute.join('|')))
    expect(attributeCombos.size).toBe(6)
  })
})
