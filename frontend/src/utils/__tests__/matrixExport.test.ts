import { describe, expect, it } from 'vitest'
import {
  buildArchiveNo,
  CARD_LAYOUTS,
  COLOR_SCHEMES,
  computeCanvasSize,
  getCardLayout,
  getColorScheme,
  pickColumns,
  STANDARD_LAYOUT,
  YITULIU_QR,
} from '@/utils/matrixExport'

describe('pickColumns', () => {
  it('条目很少时每张卡各占一列，不留空位', () => {
    expect(pickColumns(1)).toBe(1)
    expect(pickColumns(2)).toBe(2)
    expect(pickColumns(3)).toBe(3)
  })

  it('按总数分档扩列', () => {
    expect(pickColumns(4)).toBe(3)
    expect(pickColumns(8)).toBe(3)
    expect(pickColumns(9)).toBe(4)
    expect(pickColumns(18)).toBe(4)
    expect(pickColumns(19)).toBe(5)
    expect(pickColumns(40)).toBe(5)
    expect(pickColumns(41)).toBe(6)
    expect(pickColumns(200)).toBe(6)
  })

  it('总数为 0 时也要返回合法列数，避免除零', () => {
    expect(pickColumns(0)).toBe(1)
  })
})

describe('computeCanvasSize', () => {
  it('宽度只由列数决定，与条目数无关', () => {
    const few = computeCanvasSize(3, 0, 3, STANDARD_LAYOUT)
    const many = computeCanvasSize(30, 0, 3, STANDARD_LAYOUT)
    expect(few.width).toBe(many.width)
  })

  it('行数按列数向上取整', () => {
    expect(computeCanvasSize(7, 5, 3, STANDARD_LAYOUT)).toMatchObject({
      weaponRows: 3,
      customRows: 2,
    })
  })

  it('没有自定义基质时不为该区留高度', () => {
    const withCustom = computeCanvasSize(6, 3, 3, STANDARD_LAYOUT)
    const withoutCustom = computeCanvasSize(6, 0, 3, STANDARD_LAYOUT)
    expect(withoutCustom.customRows).toBe(0)
    expect(withoutCustom.height).toBeLessThan(withCustom.height)
  })

  it('只有自定义基质时不为内置武器区留高度', () => {
    const onlyCustom = computeCanvasSize(0, 3, 3, STANDARD_LAYOUT)
    const onlyWeapon = computeCanvasSize(3, 0, 3, STANDARD_LAYOUT)
    expect(onlyCustom.weaponRows).toBe(0)
    // 两区各一行、区标题各一个，缺少区间距的情况下高度应当相等
    expect(onlyCustom.height).toBe(onlyWeapon.height)
  })

  it('两区都有时高度比单区多出一个区间距', () => {
    const both = computeCanvasSize(3, 3, 3, STANDARD_LAYOUT)
    const onlyWeapon = computeCanvasSize(3, 0, 3, STANDARD_LAYOUT)
    const oneSectionExtra = both.height - onlyWeapon.height
    // 多出的部分 = 区间距 + 区标题 + 一行卡片
    expect(oneSectionExtra).toBeGreaterThan(0)
    expect(both.weaponRows).toBe(1)
    expect(both.customRows).toBe(1)
  })

  it('列数为 0 时兜底成 1 列，不产生 Infinity', () => {
    const size = computeCanvasSize(3, 0, 0, STANDARD_LAYOUT)
    expect(Number.isFinite(size.width)).toBe(true)
    expect(size.weaponRows).toBe(3)
  })

  it('画布高度跟随版式卡片高度，不同尺寸的版式产出不同高度', () => {
    // 画布高度只由版式的 cardHeight 推导：按「去重后的卡片高度数」断言，
    // 不依赖各版式高度互不相同，将来有版式共用同一高度时该断言依然成立
    const distinctCardHeights = new Set(CARD_LAYOUTS.map((layout) => layout.cardHeight)).size
    const heights = CARD_LAYOUTS.map((layout) => computeCanvasSize(6, 0, 3, layout).height)
    expect(new Set(heights).size).toBe(distinctCardHeights)
  })
})

describe('buildArchiveNo', () => {
  it('补零到三位，条目数变化时页脚宽度不跳动', () => {
    expect(buildArchiveNo(7)).toBe('EER-007-MATRIX')
    expect(buildArchiveNo(77)).toBe('EER-077-MATRIX')
    expect(buildArchiveNo(770)).toBe('EER-770-MATRIX')
  })

  it('超过三位时不截断', () => {
    expect(buildArchiveNo(1234)).toBe('EER-1234-MATRIX')
  })

  it('非法输入兜底成 0，不把 NaN 画到图上', () => {
    expect(buildArchiveNo(-5)).toBe('EER-000-MATRIX')
    expect(buildArchiveNo(Number.NaN)).toBe('EER-000-MATRIX')
    expect(buildArchiveNo(3.7)).toBe('EER-003-MATRIX')
  })
})

describe('YITULIU_QR', () => {
  // 点阵是离线生成后写死的，肉眼看不出改坏了没有，只能靠 QR 自身的固定结构兜底
  const FINDER = ['1111111', '1000001', '1011101', '1011101', '1011101', '1000001', '1111111']

  function readFinder(top: number, left: number): string[] {
    return FINDER.map((_, row) => YITULIU_QR[top + row]!.slice(left, left + FINDER.length))
  }

  it('是 25×25 的合法点阵', () => {
    expect(YITULIU_QR).toHaveLength(25)
    for (const row of YITULIU_QR) {
      expect(row).toMatch(/^[01]{25}$/)
    }
  })

  it('三个角上的定位图案完整', () => {
    expect(readFinder(0, 0)).toEqual(FINDER)
    expect(readFinder(0, 18)).toEqual(FINDER)
    expect(readFinder(18, 0)).toEqual(FINDER)
  })

  it('定时图案保持交替，解码器靠它对齐网格', () => {
    const timingRow = YITULIU_QR[6]!.slice(8, 17)
    const timingColumn = YITULIU_QR.slice(8, 17)
      .map((row) => row[6])
      .join('')
    expect(timingRow).toBe('101010101')
    expect(timingColumn).toBe('101010101')
  })
})

describe('COLOR_SCHEMES', () => {
  it('方案 id 唯一，且第一个是默认方案', () => {
    const ids = COLOR_SCHEMES.map((scheme) => scheme.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids[0]).toBe('industrial')
  })

  it('getColorScheme 按 id 命中，未知 id 回退工业档案', () => {
    for (const scheme of COLOR_SCHEMES) {
      expect(getColorScheme(scheme.id).id).toBe(scheme.id)
    }
    expect(getColorScheme('no-such-scheme').id).toBe('industrial')
  })

  it('每个方案都具备完整色板与装饰开关', () => {
    for (const scheme of COLOR_SCHEMES) {
      // 主色板 10 个字段全部非空
      for (const value of Object.values(scheme.ink)) {
        expect(value).toBeTruthy()
      }
      // 未获得色板 3 个字段
      for (const value of Object.values(scheme.dim)) {
        expect(value).toBeTruthy()
      }
      // 词条三行色各 3 个
      expect(scheme.pip.colors).toHaveLength(3)
      for (const value of scheme.pip.colors) {
        expect(value).toBeTruthy()
      }
      // 装饰开关都是布尔，水墨字字符非空
      const { brushGlyphChar, ...flags } = scheme.decorations
      for (const flag of Object.values(flags)) {
        expect(typeof flag).toBe('boolean')
      }
      expect(brushGlyphChar).toBeTruthy()
      // 切角不能是负数
      expect(scheme.cardChamfer).toBeGreaterThanOrEqual(0)
    }
  })

  it('方案之间不是同一套配色，避免选择器形同虚设', () => {
    const backgrounds = new Set(COLOR_SCHEMES.map((scheme) => scheme.ink.bg))
    expect(backgrounds.size).toBe(COLOR_SCHEMES.length)
  })
})

describe('CARD_LAYOUTS', () => {
  it('版式 id 唯一，且第一个是默认版式', () => {
    const ids = CARD_LAYOUTS.map((layout) => layout.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids[0]).toBe('standard')
  })

  it('getCardLayout 按 id 命中，未知 id 回退标准铭牌', () => {
    for (const layout of CARD_LAYOUTS) {
      expect(getCardLayout(layout.id).id).toBe(layout.id)
    }
    expect(getCardLayout('no-such-layout').id).toBe('standard')
  })

  it('每个版式都有正尺寸、说明与可调用的绘制函数', () => {
    for (const layout of CARD_LAYOUTS) {
      expect(layout.cardWidth).toBeGreaterThan(0)
      expect(layout.cardHeight).toBeGreaterThan(0)
      expect(layout.description).toBeTruthy()
      expect(typeof layout.drawCard).toBe('function')
    }
  })

  it('版式之间卡片尺寸不全相同，避免选择器形同虚设', () => {
    const heights = new Set(CARD_LAYOUTS.map((layout) => layout.cardHeight))
    expect(heights.size).toBeGreaterThan(1)
  })
})
