import type { ExportTableRow } from '@/utils/matrixExportTable'
import { describe, expect, it } from 'vitest'
import { exportRowsToCsv, exportRowsToJson } from '@/utils/matrixExportTable'

/** 6★ 武器：三个槽位齐全 */
function weaponRow(overrides: Partial<ExportTableRow> = {}): ExportTableRow {
  return {
    weaponId: 'wpn_funnel_0009',
    name: '领航者',
    source: 'builtin',
    weaponTypeName: '施术单元',
    rarity: 6,
    owned: true,
    maxed: false,
    traits: [
      { slot: 0, name: '攻击力提升', level: 4, maxLevel: 6 },
      { slot: 1, name: '暴击率提升', level: 2, maxLevel: 6 },
      { slot: 2, name: '技能急速', level: 1, maxLevel: 3 },
    ],
    includeInCalculation: true,
    priority: 6,
    essenceCount: 3,
    ...overrides,
  }
}

/** 3★ 武器：没有附加槽位，只有属性与技能 */
function threeStarRow(): ExportTableRow {
  return weaponRow({
    weaponId: 'wpn_sword_0001',
    name: '入门剑',
    rarity: 3,
    traits: [
      { slot: 0, name: '攻击力提升', level: 6, maxLevel: 6 },
      { slot: 2, name: '技能急速', level: 3, maxLevel: 3 },
    ],
    includeInCalculation: false,
    priority: 0,
    essenceCount: null,
  })
}

describe('exportRowsToCsv', () => {
  it('表头与行尾用 CRLF，末尾以换行收尾', () => {
    const csv = exportRowsToCsv([weaponRow()])
    const lines = csv.split('\r\n')

    expect(csv.endsWith('\r\n')).toBe(true)
    expect(csv).not.toContain('\r\r\n')
    expect(lines[0]!.startsWith('武器ID,名称,类型,稀有度,来源')).toBe(true)
    // 表头 + 1 行数据 + 末尾空串
    expect(lines).toHaveLength(3)
  })

  it('三个槽位按属性/附加/技能顺序展开成等级与满级两列', () => {
    const csv = exportRowsToCsv([weaponRow()])
    const cells = csv.split('\r\n')[1]!.split(',')

    expect(cells.slice(0, 7)).toEqual([
      'wpn_funnel_0009',
      '领航者',
      '施术单元',
      '6',
      '内置',
      '是',
      '否',
    ])
    expect(cells.slice(7, 16)).toEqual([
      '攻击力提升',
      '4',
      '6',
      '暴击率提升',
      '2',
      '6',
      '技能急速',
      '1',
      '3',
    ])
    expect(cells.slice(16)).toEqual(['是', '6', '3'])
  })

  it('3★ 武器缺附加槽位时该三列留空，而不是把技能挪到附加列', () => {
    const csv = exportRowsToCsv([threeStarRow()])
    const cells = csv.split('\r\n')[1]!.split(',')

    expect(cells.slice(7, 16)).toEqual(['攻击力提升', '6', '6', '', '', '', '技能急速', '3', '3'])
  })

  it('未获得的条目在 CSV 里留空参与计算与扫描数量', () => {
    const csv = exportRowsToCsv([
      weaponRow({ owned: false, includeInCalculation: null, essenceCount: null }),
    ])
    const cells = csv.split('\r\n')[1]!.split(',')

    expect(cells[5]).toBe('否')
    expect(cells[16]).toBe('')
    expect(cells[18]).toBe('')
  })

  it('自定义基质按 6★、来源写自定义，类型留空', () => {
    const csv = exportRowsToCsv([
      weaponRow({
        weaponId: 'custom:abc',
        name: '自建基质',
        source: 'custom',
        weaponTypeName: '',
        maxed: true,
      }),
    ])
    const cells = csv.split('\r\n')[1]!.split(',')

    expect(cells[2]).toBe('')
    expect(cells[3]).toBe('6')
    expect(cells[4]).toBe('自定义')
  })

  it('表头列数与数据列数一致，防止加列时只改了一边', () => {
    const [header, row] = exportRowsToCsv([weaponRow()]).split('\r\n')

    expect(header!.split(',')).toHaveLength(19)
    expect(row!.split(',')).toHaveLength(19)
  })

  it('含逗号、引号、换行的名称被正确转义', () => {
    const csv = exportRowsToCsv([weaponRow({ name: '带,逗号"和引号\n换行' })])

    expect(csv).toContain('"带,逗号""和引号\n换行"')
  })

  it('以公式前缀开头的名称被中和，不会在表格软件里被求值', () => {
    const csv = exportRowsToCsv([weaponRow({ name: "=cmd|'/C calc'!A0", weaponTypeName: '-危险' })])
    const cells = csv.split('\r\n')[1]!.split(',')

    expect(cells[1]).toBe("'=cmd|'/C calc'!A0")
    expect(cells[2]).toBe("'-危险")
  })

  it('数值列不受公式中和影响', () => {
    const cells = exportRowsToCsv([weaponRow({ priority: 3 })])
      .split('\r\n')[1]!
      .split(',')

    expect(cells[17]).toBe('3')
  })
})

describe('exportRowsToJson', () => {
  const meta = { profile: '默认账号', exportedAt: '2026-02-06T04:00:00.000Z' }

  it('顶层带账号、导出时间与条目数', () => {
    const payload = JSON.parse(exportRowsToJson([weaponRow(), threeStarRow()], meta))

    expect(payload.profile).toBe('默认账号')
    expect(payload.exported_at).toBe(meta.exportedAt)
    expect(payload.count).toBe(2)
    expect(payload.items).toHaveLength(2)
  })

  it('词条带语义槽位名，3★ 只有两条且按槽位升序', () => {
    const payload = JSON.parse(exportRowsToJson([threeStarRow()], meta))

    expect(payload.items[0].traits).toEqual([
      { slot: 'attribute', name: '攻击力提升', level: 6, max_level: 6 },
      { slot: 'skill', name: '技能急速', level: 3, max_level: 3 },
    ])
  })

  it('缺省值保留为 null 而不是被省略或改写成 0', () => {
    const payload = JSON.parse(
      exportRowsToJson(
        [
          weaponRow({
            owned: false,
            includeInCalculation: null,
            essenceCount: null,
            rarity: null,
            weaponTypeName: '',
          }),
        ],
        meta,
      ),
    )

    const item = payload.items[0]
    expect(item.include_in_calculation).toBeNull()
    expect(item.essence_count).toBeNull()
    expect(item.rarity).toBeNull()
    expect(item.weapon_type).toBeNull()
  })

  it('输出是可解析的 JSON 文本，带缩进并以换行收尾', () => {
    const text = exportRowsToJson([weaponRow()], meta)

    expect(text.endsWith('\n')).toBe(true)
    expect(text).toContain('\n  "profile"')
    expect(() => JSON.parse(text)).not.toThrow()
  })

  it('自定义基质的 source 写 custom，来源与 CSV 口径一致', () => {
    const payload = JSON.parse(
      exportRowsToJson([weaponRow({ source: 'custom', weaponTypeName: '' })], meta),
    )

    expect(payload.items[0].source).toBe('custom')
  })
})
