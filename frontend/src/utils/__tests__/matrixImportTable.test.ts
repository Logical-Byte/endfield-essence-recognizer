import type { TreasureMatrixEntry } from '@/composables/useProfiles'
import { describe, expect, it } from 'vitest'
import {
  buildImportPlan,
  canApplyPlan,
  entriesToBackupJson,
  parseImportText,
} from '@/utils/matrixImportTable'

const BUILTIN = new Map([
  ['wpn_sword_0001', '入门剑'],
  ['wpn_funnel_0009', '领航者'],
])
const CUSTOM = new Map([['custom:abc', '自建基质']])

/** 与导出 CSV 一致的表头 */
const CSV_HEADER =
  '武器ID,名称,类型,稀有度,来源,是否已获得,是否满级,属性词条,属性等级,属性满级,附加词条,附加等级,附加满级,技能词条,技能等级,技能满级,参与计算,优先级,扫描数量'

function csvRow(cells: {
  id: string
  level1?: string
  level2?: string
  level3?: string
  owned?: string
  calc?: string
  priority?: string
}): string {
  const {
    id,
    level1 = '4',
    level2 = '2',
    level3 = '1',
    owned = '是',
    calc = '是',
    priority = '0',
  } = cells
  return `${id},名字,单手剑,6,内置,${owned},否,词条${level1},${level1},6,词条${level2},${level2},6,词条${level3},${level3},3,${calc},${priority},`
}

function entry(overrides: Partial<TreasureMatrixEntry> = {}): TreasureMatrixEntry {
  return {
    weapon_id: 'wpn_funnel_0009',
    weapon_name: '领航者',
    affix1_level: 1,
    affix2_level: 1,
    affix3_level: 1,
    include_in_calculation: true,
    priority: 0,
    ...overrides,
  }
}

describe('parseImportText - CSV', () => {
  it('按表头名取值，忽略列顺序与多余列', () => {
    const text = [
      '优先级,武器ID,属性等级,附加等级,技能等级,是否已获得,未知列',
      '7,wpn_funnel_0009,5,3,2,是,xxx',
    ].join('\r\n')

    const { rows, skipped } = parseImportText(text)

    expect(skipped).toEqual([])
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({
      weaponId: 'wpn_funnel_0009',
      levels: [5, 3, 2],
      owned: true,
      priority: 7,
    })
  })

  it('剥离 BOM 并兼容 LF 行尾', () => {
    const text = `\uFEFF${CSV_HEADER}\n${csvRow({ id: 'wpn_funnel_0009' })}`

    const { rows } = parseImportText(text)

    expect(rows).toHaveLength(1)
    expect(rows[0]!.weaponId).toBe('wpn_funnel_0009')
  })

  it('字段内的逗号与引号按 CSV 规范还原', () => {
    const text = ['武器ID,名称,属性等级', '"wpn_funnel_0009","带,逗号""和引号",4'].join('\n')

    const { rows } = parseImportText(text)

    expect(rows[0]!.name).toBe('带,逗号"和引号')
  })

  it('未获得的行走 not_owned，不进入待导入行', () => {
    const text = [CSV_HEADER, csvRow({ id: 'wpn_sword_0001', owned: '否', level1: '0' })].join('\n')

    const { rows, skipped } = parseImportText(text)

    expect(rows).toEqual([])
    expect(skipped).toEqual([{ lineNumber: 2, weaponId: 'wpn_sword_0001', reason: 'not_owned' }])
  })

  it('等级越界行标记 invalid_level 并保留行号', () => {
    const text = [CSV_HEADER, csvRow({ id: 'wpn_funnel_0009', level1: '7' })].join('\n')

    const { rows, skipped } = parseImportText(text)

    expect(rows).toEqual([])
    expect(skipped).toEqual([
      { lineNumber: 2, weaponId: 'wpn_funnel_0009', reason: 'invalid_level' },
    ])
  })

  it('一列等级都读不出来时跳过整行，避免把等级洗成默认值', () => {
    const text = ['武器ID,名称', 'wpn_funnel_0009,领航者'].join('\n')

    const { rows, skipped } = parseImportText(text)

    expect(rows).toEqual([])
    expect(skipped[0]!.reason).toBe('invalid_row')
  })

  it('优先级超出 0–9 时按未设置处理，不写进账号', () => {
    const text = [CSV_HEADER, csvRow({ id: 'wpn_funnel_0009', priority: '42' })].join('\n')

    const { rows } = parseImportText(text)

    expect(rows[0]!.priority).toBeNull()
  })

  it('跳过行的行号按文件物理行计算', () => {
    // 第 3 行是空行，第 5~6 行是一个带换行的引号字段：记录下标推不出这些行号
    const text = [
      '武器ID,名称,属性等级',
      'wpn_funnel_0009,领航者,4',
      '',
      'wpn_sword_0001,入门剑,7',
      'wpn_sword_0001,"带',
      '换行的名字",3',
      ',没有ID,4',
    ].join('\n')

    const { skipped } = parseImportText(text)

    expect(skipped.map((item) => item.lineNumber)).toEqual([4, 7])
    expect(skipped.map((item) => item.reason)).toEqual(['invalid_level', 'invalid_row'])
  })

  it('缺武器ID列时整批拒绝', () => {
    expect(() => parseImportText('名称,属性等级\n领航者,4')).toThrow(/武器ID/)
  })

  it('空文件报错而不是静默成功', () => {
    expect(() => parseImportText('   \n  ')).toThrow(/空/)
  })
})

describe('parseImportText - JSON', () => {
  const payload = {
    profile: 'default',
    count: 2,
    items: [
      {
        weapon_id: 'wpn_funnel_0009',
        name: '领航者',
        owned: true,
        include_in_calculation: false,
        priority: 6,
        traits: [
          { slot: 'attribute', level: 4 },
          { slot: 'secondary', level: 2 },
          { slot: 'skill', level: 1 },
        ],
      },
      {
        weapon_id: 'wpn_sword_0001',
        owned: true,
        traits: [
          { slot: 'attribute', level: 6 },
          { slot: 'skill', level: 3 },
        ],
      },
    ],
  }

  it('读 items、槽位名与缺省字段', () => {
    const { rows, skipped } = parseImportText(JSON.stringify(payload))

    expect(skipped).toEqual([])
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({
      weaponId: 'wpn_funnel_0009',
      levels: [4, 2, 1],
      includeInCalculation: false,
      priority: 6,
    })
    // 3★ 没有附加槽位，中间为 null
    expect(rows[1]!.levels).toEqual([6, null, 3])
    expect(rows[1]!.priority).toBeNull()
  })

  it('接受裸数组与数字槽位', () => {
    const text = JSON.stringify([
      {
        weapon_id: 'wpn_sword_0001',
        traits: [
          { slot: 0, level: 5 },
          { slot: 2, level: 2 },
        ],
      },
    ])

    const { rows } = parseImportText(text)

    expect(rows[0]!.levels).toEqual([5, null, 2])
  })

  it('未获得与越界等级分别跳过', () => {
    const text = JSON.stringify({
      items: [
        { weapon_id: 'a', owned: false, traits: [{ slot: 0, level: 1 }] },
        { weapon_id: 'b', traits: [{ slot: 2, level: 9 }] },
      ],
    })

    const { rows, skipped } = parseImportText(text)

    expect(rows).toEqual([])
    expect(skipped.map((item) => item.reason)).toEqual(['not_owned', 'invalid_level'])
  })

  it('不是导入格式的 JSON 明确报错', () => {
    expect(() => parseImportText('{"foo": 1}')).toThrow(/items/)
    expect(() => parseImportText('{bad')).toThrow(/JSON/)
  })
})

describe('buildImportPlan', () => {
  const base = {
    builtinNames: BUILTIN,
    customNames: CUSTOM,
    existing: [] as TreasureMatrixEntry[],
    weaponPriorities: {} as Record<string, number>,
  }

  it('合并模式按 weapon_id 覆盖，文件外的条目保持原样', () => {
    const parsed = parseImportText(
      [CSV_HEADER, csvRow({ id: 'wpn_funnel_0009', level1: '5' })].join('\n'),
    )

    const plan = buildImportPlan({
      ...base,
      ...parsed,
      existing: [entry(), entry({ weapon_id: 'wpn_other', weapon_name: '别的' })],
      mode: 'merge',
    })

    expect(plan.added).toEqual([])
    expect(plan.updated).toHaveLength(1)
    expect(plan.entries).toHaveLength(2)
    expect(plan.entries[0]).toMatchObject({ weapon_id: 'wpn_funnel_0009', affix1_level: 5 })
    expect(plan.entries[1]!.weapon_id).toBe('wpn_other')
  })

  it('合并模式把新武器追加到末尾', () => {
    const parsed = parseImportText(
      [CSV_HEADER, csvRow({ id: 'wpn_sword_0001', level1: '3' })].join('\n'),
    )

    const plan = buildImportPlan({
      ...base,
      ...parsed,
      existing: [entry()],
      mode: 'merge',
    })

    expect(plan.added.map((item) => item.weapon_id)).toEqual(['wpn_sword_0001'])
    expect(plan.entries.map((item) => item.weapon_id)).toEqual([
      'wpn_funnel_0009',
      'wpn_sword_0001',
    ])
  })

  it('文件没写优先级时沿用现有值', () => {
    const missing = parseImportText(['武器ID,属性等级', 'wpn_sword_0001,4'].join('\n'))
    const planMissing = buildImportPlan({
      ...base,
      ...missing,
      existing: [entry({ weapon_id: 'wpn_sword_0001', priority: 8 })],
      mode: 'merge',
    })

    expect(planMissing.entries[0]!.priority).toBe(8)
  })

  it('文件里写 0 也不清除优先级：0 在导出里表示未设置', () => {
    const explicit = parseImportText(
      [CSV_HEADER, csvRow({ id: 'wpn_sword_0001', priority: '0' })].join('\n'),
    )
    const planExplicit = buildImportPlan({
      ...base,
      ...explicit,
      existing: [entry({ weapon_id: 'wpn_sword_0001', priority: 8 })],
      mode: 'merge',
    })

    expect(planExplicit.entries[0]!.priority).toBe(8)
  })

  it('未拥有基质、只存了优先级的武器导入时保留该优先级', () => {
    // 回归：此前只在矩阵条目里找优先级，未拥有基质的武器导入后会被按 0 写回，
    // 连带 weapon_priorities 里的用户偏好一起被后端清掉。
    const parsed = parseImportText(
      [CSV_HEADER, csvRow({ id: 'wpn_sword_0001', priority: '0' })].join('\n'),
    )

    const plan = buildImportPlan({
      ...base,
      ...parsed,
      existing: [],
      weaponPriorities: { wpn_sword_0001: 7 },
      mode: 'merge',
    })

    expect(plan.entries[0]!.priority).toBe(7)
  })

  it('文件里显式写了优先级时以文件为准', () => {
    const parsed = parseImportText(
      [CSV_HEADER, csvRow({ id: 'wpn_sword_0001', priority: '3' })].join('\n'),
    )

    const plan = buildImportPlan({
      ...base,
      ...parsed,
      existing: [],
      weaponPriorities: { wpn_sword_0001: 7 },
      mode: 'merge',
    })

    expect(plan.entries[0]!.priority).toBe(3)
  })

  it('文件缺某个等级列时保留原条目的等级，不用 1 覆盖', () => {
    // 回归：此前缺列一律落成 1，会把已有进度洗掉
    const parsed = parseImportText(['武器ID,属性等级', 'wpn_funnel_0009,5'].join('\n'))

    const plan = buildImportPlan({
      ...base,
      ...parsed,
      existing: [
        entry({ weapon_id: 'wpn_funnel_0009', affix1_level: 2, affix2_level: 6, affix3_level: 3 }),
      ],
      mode: 'merge',
    })

    expect(plan.entries[0]).toMatchObject({
      affix1_level: 5,
      affix2_level: 6,
      affix3_level: 3,
    })
  })

  it('新武器缺列时仍按默认 1 补齐', () => {
    const parsed = parseImportText(['武器ID,属性等级', 'wpn_sword_0001,4'].join('\n'))

    const plan = buildImportPlan({ ...base, ...parsed, existing: [], mode: 'merge' })

    expect(plan.entries[0]).toMatchObject({
      affix1_level: 4,
      affix2_level: 1,
      affix3_level: 1,
    })
  })

  it('替换模式以文件为准，并统计将删除的条目', () => {
    const parsed = parseImportText([CSV_HEADER, csvRow({ id: 'wpn_sword_0001' })].join('\n'))

    const plan = buildImportPlan({
      ...base,
      ...parsed,
      existing: [entry(), entry({ weapon_id: 'wpn_other', weapon_name: '别的' })],
      mode: 'replace',
    })

    expect(plan.entries.map((item) => item.weapon_id)).toEqual(['wpn_sword_0001'])
    expect(plan.removed.map((item) => item.weapon_id)).toEqual(['wpn_funnel_0009', 'wpn_other'])
  })

  it('未知武器与缺失的自定义基质分别计入跳过', () => {
    const parsed = parseImportText(
      [CSV_HEADER, csvRow({ id: 'wpn_ghost' }), csvRow({ id: 'custom:gone' })].join('\n'),
    )

    const plan = buildImportPlan({ ...base, ...parsed, existing: [], mode: 'merge' })

    expect(plan.entries).toEqual([])
    expect(plan.skipped.map((item) => item.reason)).toEqual(['unknown_weapon', 'missing_custom'])
  })

  it('本机存在的自定义基质可以正常导入', () => {
    const parsed = parseImportText([CSV_HEADER, csvRow({ id: 'custom:abc' })].join('\n'))

    const plan = buildImportPlan({ ...base, ...parsed, existing: [], mode: 'merge' })

    expect(plan.entries[0]).toMatchObject({ weapon_id: 'custom:abc', weapon_name: '自建基质' })
  })

  it('内置武器名以静态数据为准，而不是文件里的旧名字', () => {
    const parsed = parseImportText(['武器ID,名称,属性等级', 'wpn_sword_0001,旧名字,3'].join('\n'))

    const plan = buildImportPlan({ ...base, ...parsed, existing: [], mode: 'merge' })

    expect(plan.entries[0]!.weapon_name).toBe('入门剑')
  })

  it('同一把武器在文件里重复时以最后一行为准', () => {
    const parsed = parseImportText(
      [
        CSV_HEADER,
        csvRow({ id: 'wpn_sword_0001', level1: '2' }),
        csvRow({ id: 'wpn_sword_0001', level1: '5' }),
      ].join('\n'),
    )

    const plan = buildImportPlan({ ...base, ...parsed, existing: [], mode: 'merge' })

    expect(plan.entries).toHaveLength(1)
    expect(plan.entries[0]!.affix1_level).toBe(5)
  })
})

describe('canApplyPlan', () => {
  const emptyPlan = {
    entries: [] as TreasureMatrixEntry[],
    added: [] as TreasureMatrixEntry[],
    updated: [] as TreasureMatrixEntry[],
    removed: [] as TreasureMatrixEntry[],
    skipped: [],
  }

  it('合并模式下空计划不可提交', () => {
    expect(canApplyPlan(emptyPlan, 'merge')).toBe(false)
  })

  it('替换模式下会删条目时即使文件为空也可提交（用于清空/恢复空白配置）', () => {
    expect(canApplyPlan({ ...emptyPlan, removed: [entry()] }, 'replace')).toBe(true)
  })

  it('替换模式下文件与现有配置都为空时不可提交', () => {
    expect(canApplyPlan(emptyPlan, 'replace')).toBe(false)
  })

  it('有新增或更新时可提交', () => {
    expect(canApplyPlan({ ...emptyPlan, added: [entry()] }, 'merge')).toBe(true)
    expect(canApplyPlan({ ...emptyPlan, updated: [entry()] }, 'replace')).toBe(true)
  })
})

describe('entriesToBackupJson', () => {
  it('产出的快照能被自己重新解析回来', () => {
    const snapshot = entriesToBackupJson(
      'default',
      [entry({ affix1_level: 6, priority: 3 })],
      '2026-02-06T04:00:00.000Z',
    )

    const { rows, skipped } = parseImportText(snapshot)

    expect(skipped).toEqual([])
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({
      weaponId: 'wpn_funnel_0009',
      levels: [6, 1, 1],
      owned: true,
      priority: 3,
    })
  })

  it('带回账号名与时间戳，方便识别来源', () => {
    const payload = JSON.parse(entriesToBackupJson('主账号', [], '2026-02-06T04:00:00.000Z'))

    expect(payload).toMatchObject({
      profile: '主账号',
      exported_at: '2026-02-06T04:00:00.000Z',
      count: 0,
      items: [],
    })
  })
})
