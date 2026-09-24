/**
 * 重合检测组合式函数测试。
 *
 * 覆盖此前造成数据错乱的三类情况：
 * - 「不再提示」标记因删除导致下标偏移而打到别的基质上
 * - 同一基质匹配多把武器时被重复计入删除，误删相邻条目
 * - 切换到内置武器时丢失优先级
 */

import type { TreasureMatrixEntry } from '../useProfiles'

import type { CustomStat } from '@/utils/gameData/weapon'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useStaticData } from '@/utils/gameData/staticData'
import { toCustomStatId } from '@/utils/gameData/weapon'
import { __resetOverlapStateForTests, useOverlapDetection } from '../useOverlapDetection'
import { __resetProfilesStateForTests } from '../useProfiles'
import { useToast } from '../useToast'

function makeStat(id: string, name: string): CustomStat {
  return { id, name, attribute: 'atk', secondary: 'def', skill: 'ult' }
}

function makeEntry(
  weaponId: string,
  overrides: Partial<TreasureMatrixEntry> = {},
): TreasureMatrixEntry {
  return {
    weapon_id: weaponId,
    weapon_name: weaponId,
    affix1_level: 1,
    affix2_level: 1,
    affix3_level: 1,
    ...overrides,
  }
}

/** 捕获 postCustomStatsUpdate / updateTreasureMatrix 实际提交的内容 */
function stubFetch() {
  const submitted = {
    stats: null as CustomStat[] | null,
    matrix: null as TreasureMatrixEntry[] | null,
  }

  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/config' && (!init || init.method !== 'POST')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ version: 8, treasure_essence_stats: [] }),
        text: async () => '{}',
      } as unknown as Response
    }
    if (url === '/api/config' && init?.method === 'POST') {
      submitted.stats = JSON.parse(String(init.body)).treasure_essence_stats
      return { ok: true, status: 200, text: async () => '{}' } as unknown as Response
    }
    if (url === '/api/profiles/treasure_matrix') {
      submitted.matrix = JSON.parse(String(init!.body)).entries
      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({ version: 1, name: 'default', treasure_matrix: submitted.matrix }),
      } as unknown as Response
    }
    if (url === '/api/profiles/compare_levels') {
      return { ok: true, status: 200, json: async () => ({ results: [] }) } as unknown as Response
    }
    throw new Error(`未预期的请求: ${url}`)
  })

  vi.stubGlobal('fetch', fetchMock)
  return submitted
}

describe('confirmOverlapActions', () => {
  beforeEach(() => {
    __resetOverlapStateForTests()
    __resetProfilesStateForTests()
    useToast().clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('删除与「不再提示」同时存在时，标记仍落在正确的基质上', async () => {
    const submitted = stubFetch()
    const customStats = [
      makeStat('a', '甲'),
      makeStat('b', '乙'),
      makeStat('c', '丙'),
      makeStat('d', '丁'),
    ]
    const { overlapItems, confirmOverlapActions } = useOverlapDetection()

    overlapItems.value = [
      {
        customStatId: 'a',
        customName: '甲',
        customWeaponId: toCustomStatId({ id: 'a' }),
        matchedWeaponIds: ['w1'],
        matchedWeaponNames: ['W1'],
        action: 'delete',
        switchTargetId: 'w1',
      },
      {
        customStatId: 'c',
        customName: '丙',
        customWeaponId: toCustomStatId({ id: 'c' }),
        matchedWeaponIds: ['w2'],
        matchedWeaponNames: ['W2'],
        action: 'suppress',
        switchTargetId: 'w2',
      },
    ]

    await confirmOverlapActions({
      customStats,
      treasureMatrix: [],
      matrixEntryByWeaponId: new Map(),
    })

    // 甲被删除；丙（而不是删除后顶上来的丁）被标记为不再提示
    expect(submitted.stats!.map((s) => s.id)).toEqual(['b', 'c', 'd'])
    const suppressed = submitted.stats!.filter((s) => s.no_prompt_switch)
    expect(suppressed.map((s) => s.id)).toEqual(['c'])
  })

  it('同一基质匹配多把武器时只删除自身，不波及相邻条目', async () => {
    const submitted = stubFetch()
    const customStats = [makeStat('a', '甲'), makeStat('b', '乙'), makeStat('c', '丙')]
    const { overlapItems, confirmOverlapActions } = useOverlapDetection()

    // 一个基质对应多把同词条武器，聚合成单条待决策项
    overlapItems.value = [
      {
        customStatId: 'b',
        customName: '乙',
        customWeaponId: toCustomStatId({ id: 'b' }),
        matchedWeaponIds: ['w1', 'w2', 'w3'],
        matchedWeaponNames: ['W1', 'W2', 'W3'],
        action: 'delete',
        switchTargetId: 'w1',
      },
    ]

    await confirmOverlapActions({
      customStats,
      treasureMatrix: [],
      matrixEntryByWeaponId: new Map(),
    })

    expect(submitted.stats!.map((s) => s.id)).toEqual(['a', 'c'])
  })

  it('切换到内置武器时保留等级与优先级', async () => {
    const submitted = stubFetch()
    const customStats = [makeStat('a', '甲')]
    const customWeaponId = toCustomStatId({ id: 'a' })
    const entry = makeEntry(customWeaponId, {
      affix1_level: 5,
      affix2_level: 4,
      affix3_level: 3,
      priority: 7,
      include_in_calculation: false,
    })

    const { overlapItems, confirmOverlapActions } = useOverlapDetection()
    overlapItems.value = [
      {
        customStatId: 'a',
        customName: '甲',
        customWeaponId,
        matchedWeaponIds: ['w1', 'w2'],
        matchedWeaponNames: ['W1', 'W2'],
        action: 'switch',
        switchTargetId: 'w2',
      },
    ]

    await confirmOverlapActions({
      customStats,
      treasureMatrix: [entry],
      matrixEntryByWeaponId: new Map([[customWeaponId, entry]]),
    })

    const moved = submitted.matrix!.find((e) => e.weapon_id === 'w2')
    expect(moved).toMatchObject({
      affix1_level: 5,
      affix2_level: 4,
      affix3_level: 3,
      priority: 7,
      include_in_calculation: false,
    })
    // 原自定义条目已移除
    expect(submitted.matrix!.some((e) => e.weapon_id === customWeaponId)).toBe(false)
    expect(submitted.stats).toEqual([])
  })

  it('目标武器已有基质时不覆盖其数据', async () => {
    const submitted = stubFetch()
    const customWeaponId = toCustomStatId({ id: 'a' })
    const customEntry = makeEntry(customWeaponId, { affix1_level: 2 })
    const existing = makeEntry('w1', { affix1_level: 6, weapon_name: '已有' })

    const { overlapItems, confirmOverlapActions } = useOverlapDetection()
    overlapItems.value = [
      {
        customStatId: 'a',
        customName: '甲',
        customWeaponId,
        matchedWeaponIds: ['w1'],
        matchedWeaponNames: ['W1'],
        action: 'switch',
        switchTargetId: 'w1',
      },
    ]

    await confirmOverlapActions({
      customStats: [makeStat('a', '甲')],
      treasureMatrix: [customEntry, existing],
      matrixEntryByWeaponId: new Map([
        [customWeaponId, customEntry],
        ['w1', existing],
      ]),
    })

    const w1Entries = submitted.matrix!.filter((e) => e.weapon_id === 'w1')
    expect(w1Entries).toHaveLength(1)
    expect(w1Entries[0]!.affix1_level).toBe(6)
  })

  it('全部选择忽略时不发起任何提交', async () => {
    const submitted = stubFetch()
    const { overlapItems, confirmOverlapActions } = useOverlapDetection()
    overlapItems.value = [
      {
        customStatId: 'a',
        customName: '甲',
        customWeaponId: toCustomStatId({ id: 'a' }),
        matchedWeaponIds: ['w1'],
        matchedWeaponNames: ['W1'],
        action: 'ignore',
        switchTargetId: 'w1',
      },
    ]

    const result = await confirmOverlapActions({
      customStats: [makeStat('a', '甲')],
      treasureMatrix: [],
      matrixEntryByWeaponId: new Map(),
    })

    expect(result).toEqual({ deletedIds: [], suppressedIds: [] })
    expect(submitted.stats).toBeNull()
    expect(submitted.matrix).toBeNull()
  })
})

describe('checkCustomOverlap', () => {
  beforeEach(() => {
    __resetOverlapStateForTests()
    // 用与 makeStat 相同的词条填充静态数据，让自定义基质能匹配到内置武器
    const { weaponsMap } = useStaticData()
    weaponsMap.value = new Map([
      [
        'w1',
        {
          id: 'w1',
          name: 'W1',
          iconUrl: '',
          rarity: 5,
          attributeStatId: 'atk',
          secondaryStatId: 'def',
          skillStatId: 'ult',
        },
      ],
    ])
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('自动检测跳过已标记「不再提示」的条目', async () => {
    const submitted = stubFetch()
    const { overlapDialog, overlapItems, checkCustomOverlap } = useOverlapDetection()
    const customStats = [makeStat('a', '甲'), { ...makeStat('b', '乙'), no_prompt_switch: true }]

    await checkCustomOverlap(customStats, new Map())

    expect(overlapDialog.value).toBe(true)
    expect(overlapItems.value.map((i) => i.customStatId)).toEqual(['a'])
    expect(submitted.matrix).toBeNull()
  })

  it('全部条目都已标记时自动检测不弹窗', () => {
    // 该分支在请求前返回，无需 stub fetch
    const { overlapDialog, overlapItems, checkCustomOverlap } = useOverlapDetection()
    const customStats = [{ ...makeStat('b', '乙'), no_prompt_switch: true }]

    checkCustomOverlap(customStats, new Map())

    expect(overlapDialog.value).toBe(false)
    expect(overlapItems.value).toEqual([])
  })

  it('手动检测（includeSuppressed）仍显示已标记「不再提示」的条目', async () => {
    const submitted = stubFetch()
    const { overlapDialog, overlapItems, checkCustomOverlap } = useOverlapDetection()
    const suppressed = { ...makeStat('b', '乙'), no_prompt_switch: true }
    const customStats = [makeStat('a', '甲'), suppressed]

    await checkCustomOverlap(customStats, new Map(), { includeSuppressed: true })

    expect(overlapDialog.value).toBe(true)
    expect(overlapItems.value.map((i) => i.customStatId)).toEqual(['a', 'b'])
    expect(submitted.matrix).toBeNull()
  })
})

describe('autoSelectOverlap', () => {
  beforeEach(() => {
    __resetOverlapStateForTests()
  })

  it('比较结果未就绪时不做任何选择', () => {
    const { overlapItems, autoSelectOverlap } = useOverlapDetection()
    overlapItems.value = [
      {
        customStatId: 'a',
        customName: '甲',
        customWeaponId: toCustomStatId({ id: 'a' }),
        matchedWeaponIds: ['w1'],
        matchedWeaponNames: ['W1'],
        action: 'ignore',
        switchTargetId: 'w1',
      },
    ]

    autoSelectOverlap()

    // 结果没到就把所有项判成"忽略"，看起来与逐条确认过毫无区别
    expect(overlapItems.value[0]!.action).toBe('ignore')
  })

  it('结果就绪后按比较值选择动作', () => {
    const { overlapItems, overlapCompareResults, overlapCompareReady, autoSelectOverlap } =
      useOverlapDetection()
    overlapItems.value = ['a', 'b', 'c'].map((id) => ({
      customStatId: id,
      customName: id,
      customWeaponId: toCustomStatId({ id }),
      matchedWeaponIds: ['w1'],
      matchedWeaponNames: ['W1'],
      action: 'ignore' as const,
      switchTargetId: 'w1',
    }))
    overlapCompareResults.value = new Map([
      [0, 1],
      [1, 0],
      [2, -1],
    ])
    overlapCompareReady.value = true

    autoSelectOverlap()

    expect(overlapItems.value.map((i) => i.action)).toEqual(['switch', 'ignore', 'delete'])
  })
})
