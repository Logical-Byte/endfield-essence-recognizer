/**
 * 自定义基质标识工具测试。
 *
 * 这些函数是全前端唯一解析自定义基质 ID 的入口，一旦解析错位，
 * 界面上的名称、图标和等级都会张冠李戴，因此逐条锁定行为。
 */

import type { CustomStat } from '../weapon'

import { describe, expect, it } from 'vitest'
import { useStaticData } from '../staticData'
import {
  buildFullCustomStatMatrix,
  buildStatKey,
  createCustomStatId,
  CUSTOM_ID_PREFIX,
  fallbackCustomStatName,
  findCustomStat,
  isCustomStatId,
  toCustomStatId,
} from '../weapon'

function makeStat(id: string, name?: string): CustomStat {
  return { id, name, attribute: null, secondary: null, skill: null }
}

const STATS: CustomStat[] = [makeStat('aaa', '甲'), makeStat('bbb', '乙'), makeStat('ccc')]

describe('isCustomStatId', () => {
  it('识别新格式', () => {
    expect(isCustomStatId('custom:aaa')).toBe(true)
  })

  it('兼容识别迁移前的旧格式', () => {
    expect(isCustomStatId('custom_stat_0')).toBe(true)
  })

  it('普通武器与空值返回 false', () => {
    expect(isCustomStatId('wpn_001')).toBe(false)
    expect(isCustomStatId(null)).toBe(false)
    expect(isCustomStatId(undefined)).toBe(false)
    expect(isCustomStatId('')).toBe(false)
  })
})

describe('findCustomStat', () => {
  it('按 ID 命中，与所在下标无关', () => {
    const found = findCustomStat('custom:bbb', STATS)
    expect(found?.stat.name).toBe('乙')
    expect(found?.index).toBe(1)
  })

  it('删除前面的条目后，同一个 ID 仍指向同一条记录', () => {
    // 这正是稳定 ID 要解决的问题：下标变了，引用不该跟着错位
    const afterDelete = STATS.slice(1)
    const found = findCustomStat('custom:bbb', afterDelete)
    expect(found?.stat.name).toBe('乙')
    expect(found?.index).toBe(0)
  })

  it('ID 不存在时返回 null', () => {
    expect(findCustomStat('custom:missing', STATS)).toBeNull()
  })

  it('旧格式按下标兜底解析', () => {
    expect(findCustomStat('custom_stat_2', STATS)?.stat.id).toBe('ccc')
  })

  it('旧格式下标越界返回 null', () => {
    expect(findCustomStat('custom_stat_9', STATS)).toBeNull()
  })

  it('旧格式后缀非数字返回 null', () => {
    expect(findCustomStat('custom_stat_abc', STATS)).toBeNull()
  })

  it('普通武器 ID 与空值返回 null', () => {
    expect(findCustomStat('wpn_001', STATS)).toBeNull()
    expect(findCustomStat(null, STATS)).toBeNull()
  })
})

describe('toCustomStatId', () => {
  it('拼接前缀', () => {
    expect(toCustomStatId({ id: 'xyz' })).toBe(`${CUSTOM_ID_PREFIX}xyz`)
  })

  it('与 findCustomStat 互为逆运算', () => {
    for (const stat of STATS) {
      expect(findCustomStat(toCustomStatId(stat), STATS)?.stat.id).toBe(stat.id)
    }
  })
})

describe('createCustomStatId', () => {
  it('生成非空且互不相同的 ID', () => {
    const ids = new Set(Array.from({ length: 50 }, () => createCustomStatId()))
    expect(ids.size).toBe(50)
    expect([...ids].every((id) => id.length > 0)).toBe(true)
  })

  it('生成的 ID 可被 findCustomStat 正确检索', () => {
    const stat = makeStat(createCustomStatId(), '新建')
    expect(findCustomStat(toCustomStatId(stat), [stat])?.stat.name).toBe('新建')
  })
})

describe('buildStatKey', () => {
  it('内置武器与自定义基质的同类字段生成相同键', () => {
    // 连线层用该键把自定义基质与内置武器互相匹配，格式必须一致
    expect(buildStatKey('gem_attr', 'gem_sec', 'gem_skill')).toBe('gem_attr|gem_sec|gem_skill')
  })

  it('空属性用 null 占位，仍能与内置武器的空字段匹配', () => {
    expect(buildStatKey(null, 'gem_sec', null)).toBe('null|gem_sec|null')
  })

  it('不同顺序/不同值生成不同键', () => {
    expect(buildStatKey('a', 'b', 'c')).not.toBe(buildStatKey('a', 'c', 'b'))
  })
})

describe('fallbackCustomStatName', () => {
  it('按 1 起编号', () => {
    expect(fallbackCustomStatName(0)).toBe('自定义基质 1')
    expect(fallbackCustomStatName(4)).toBe('自定义基质 5')
  })
})

describe('buildFullCustomStatMatrix', () => {
  const ATTRIBUTES = ['gat_passive_attr_agi', 'gat_passive_attr_main']
  const SECONDARIES = ['gat_passive_attr_atk', 'gat_passive_attr_firedam', 'gat_passive_attr_usp']
  const SKILLS = ['gst_passive_tacafter', 'gst_passive_ult']

  /** 装载短名所依赖的词条静态数据，未装载时 getGemTagName 只会回显 ID */
  function loadEssences() {
    const { essencesMap } = useStaticData()
    essencesMap.value = new Map(
      (
        [
          ['gat_passive_attr_agi', '敏捷提升', 'ATTRIBUTE'],
          ['gat_passive_attr_main', '主能力提升', 'ATTRIBUTE'],
          ['gat_passive_attr_atk', '攻击提升', 'SECONDARY'],
          ['gat_passive_attr_firedam', '灼热伤害提升', 'SECONDARY'],
          ['gat_passive_attr_usp', '终结技充能效率提升', 'SECONDARY'],
          ['gst_passive_tacafter', '流转', 'SKILL'],
          ['gst_passive_ult', '夜幕', 'SKILL'],
        ] as const
      ).map(([id, name, type]) => [id, { id, name, tagName: name, type }]),
    )
  }

  it('生成三个维度的笛卡尔积', () => {
    loadEssences()
    const generated = buildFullCustomStatMatrix(ATTRIBUTES, SECONDARIES, SKILLS, new Set())
    expect(generated).toHaveLength(2 * 3 * 2)
    const keys = new Set(generated.map((s) => buildStatKey(s.attribute, s.secondary, s.skill)))
    expect(keys.size).toBe(12)
  })

  it('跳过已被占用的属性组合', () => {
    loadEssences()
    const occupied = new Set([
      buildStatKey('gat_passive_attr_agi', 'gat_passive_attr_atk', 'gst_passive_ult'),
    ])
    const generated = buildFullCustomStatMatrix(ATTRIBUTES, SECONDARIES, SKILLS, occupied)
    expect(generated).toHaveLength(11)
    expect(
      generated.some((s) => buildStatKey(s.attribute, s.secondary, s.skill) === [...occupied][0]),
    ).toBe(false)
  })

  it('按「基础 2 字 + 附加 2 字 + 技能 1 字」命名', () => {
    loadEssences()
    const generated = buildFullCustomStatMatrix(ATTRIBUTES, SECONDARIES, SKILLS, new Set())
    const names = generated.map((s) => s.name)
    expect(names.every((name) => name?.length === 5)).toBe(true)
    // 属性通用规则：去「提升」后缀；技能查简称表（流转 → 流）
    expect(names).toContain('敏捷攻击流')
    // 属性通用规则：再去「伤害」后缀；技能简称取末字（夜幕 → 夜）
    expect(names).toContain('敏捷灼热夜')
    // 属性截断到 2 字（主能力提升 → 主能）+ 属性覆盖表（终结技充能效率提升 → 充能）
    expect(names).toContain('主能充能流')
  })

  it('每条都带互不相同的稳定 ID', () => {
    loadEssences()
    const generated = buildFullCustomStatMatrix(ATTRIBUTES, SECONDARIES, SKILLS, new Set())
    expect(new Set(generated.map((s) => s.id)).size).toBe(generated.length)
  })

  it('全部组合都被占用时返回空列表', () => {
    loadEssences()
    const occupied = new Set(
      ATTRIBUTES.flatMap((a) =>
        SECONDARIES.flatMap((s) => SKILLS.map((k) => buildStatKey(a, s, k))),
      ),
    )
    expect(buildFullCustomStatMatrix(ATTRIBUTES, SECONDARIES, SKILLS, occupied)).toEqual([])
  })
})
