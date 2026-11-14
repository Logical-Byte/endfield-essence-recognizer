/**
 * 宝藏基质导出表格的序列化模块（CSV / JSON）。
 *
 * 与 matrixExport.ts 的分工：那边把卡片画成图片，这里把同一批卡片写成文本，
 * 两者共用弹窗里的筛选结果，导出的条目集合天然一致。
 * 本模块不感知任何应用状态，输入是普通行对象，能在 node 环境的单测里直接跑。
 */

/** 语义槽位：0=属性、1=附加、2=技能，与 ExportTrait.slot 对齐 */
const TRAIT_SLOTS = [0, 1, 2] as const

/** 语义槽位 → JSON 里的槽位名 */
const TRAIT_SLOT_KEYS: Record<number, string> = {
  0: 'attribute',
  1: 'secondary',
  2: 'skill',
}

/** CSV 表头，顺序与 buildCsvCells 的列顺序一一对应 */
const CSV_HEADERS = [
  '武器ID',
  '名称',
  '类型',
  '稀有度',
  '来源',
  '是否已获得',
  '是否满级',
  '属性词条',
  '属性等级',
  '属性满级',
  '附加词条',
  '附加等级',
  '附加满级',
  '技能词条',
  '技能等级',
  '技能满级',
  '参与计算',
  '优先级',
  '扫描数量',
] as const

/** 表格里的单个词条；3★ 武器没有附加槽位，所以行内可能只有两条 */
export interface ExportTableTrait {
  /** 语义槽位：0=属性、1=附加、2=技能 */
  slot: number
  /** 词条中文名 */
  name: string
  /** 当前等级 */
  level: number
  /** 满级 */
  maxLevel: number
}

/** 表格里的一行，对应导出图里的一张卡片 */
export interface ExportTableRow {
  /** 武器 ID，内置武器与自定义基质都是稳定主键 */
  weaponId: string
  name: string
  /** 内置武器或自定义基质；JSON 里取 builtin / custom */
  source: 'builtin' | 'custom'
  /** 武器类型名称；自定义基质没有类型，为空串 */
  weaponTypeName: string
  /** 稀有度；自定义基质按 6 处理，未知为 null */
  rarity: number | null
  owned: boolean
  maxed: boolean
  /** 逐词条的等级数据 */
  traits: readonly ExportTableTrait[]
  /** 是否参与刷取建议计算；未获得的条目没有配置，为 null */
  includeInCalculation: boolean | null
  /** 用户手动设置的优先级，0 表示未设置 */
  priority: number
  /** 本次运行的扫描数量；没有对应数据为 null */
  essenceCount: number | null
}

/** JSON 顶层的元信息 */
export interface ExportTableMeta {
  /** 当前账号名 */
  profile: string
  /** 导出时间，ISO 8601（UTC） */
  exportedAt: string
}

/** 按语义槽位取词条，缺失（3★ 没有附加）时返回 undefined */
function traitAtSlot(row: ExportTableRow, slot: number): ExportTableTrait | undefined {
  return row.traits.find((trait) => trait.slot === slot)
}

/** 布尔量在 CSV 里写成人读的中文；null 留空，表示没有对应数据 */
function formatFlag(value: boolean | null): string {
  if (value === null) return ''
  return value ? '是' : '否'
}

/** 可空数值在 CSV 里留空而不是写 null */
function formatOptionalNumber(value: number | null): string {
  return value === null ? '' : String(value)
}

/**
 * 转义单个 CSV 单元格。
 *
 * 只在含逗号、引号或换行时才加引号，其余保持裸值，Excel 里看起来更干净；
 * 引号按 CSV 规范双写。
 */
function escapeCsvCell(value: string): string {
  if (!/[",\r\n]/.test(value)) return value
  return `"${value.replaceAll('"', '""')}"`
}

/** 会被表格软件当成公式求值的起始字符 */
const FORMULA_PREFIX = /^[=+\-@\t\r]/

/**
 * 中和表格公式注入。
 *
 * 自定义基质名是用户可编辑的自由文本，形如 `=cmd|...` 的名字在 Excel/WPS
 * 里会被当公式执行，而 CSV 的引号只解决「字段怎么切分」，挡不住它。按表格
 * 软件的约定在最前面加一个单引号，单元格就按纯文本显示。
 *
 * 只作用于文本列（武器ID / 名称 / 类型 / 词条名）：数值列由本模块自己生成，
 * 不可能是公式。导入侧只用武器ID 与等级列，所以加前缀不影响往返。
 */
function neutralizeFormula(value: string): string {
  return FORMULA_PREFIX.test(value) ? `'${value}` : value
}

/** 把一行展开成与 CSV_HEADERS 等长的单元格数组 */
function buildCsvCells(row: ExportTableRow): string[] {
  const traitCells = TRAIT_SLOTS.flatMap((slot) => {
    const trait = traitAtSlot(row, slot)
    return [
      neutralizeFormula(trait?.name ?? ''),
      trait ? String(trait.level) : '',
      trait ? String(trait.maxLevel) : '',
    ]
  })

  return [
    neutralizeFormula(row.weaponId),
    neutralizeFormula(row.name),
    neutralizeFormula(row.weaponTypeName),
    formatOptionalNumber(row.rarity),
    row.source === 'custom' ? '自定义' : '内置',
    formatFlag(row.owned),
    formatFlag(row.maxed),
    ...traitCells,
    formatFlag(row.includeInCalculation),
    String(row.priority),
    formatOptionalNumber(row.essenceCount),
  ]
}

/**
 * 序列化成 CSV 文本。
 *
 * 行尾用 CRLF：Excel 与 Windows 记事本对纯 LF 的兼容性更差。
 * BOM 不在这里加——落盘那一层统一补，避免同一份内容两条代码路径各补一次。
 */
export function exportRowsToCsv(rows: readonly ExportTableRow[]): string {
  const lines = [CSV_HEADERS.join(',')]
  for (const row of rows) {
    lines.push(
      buildCsvCells(row)
        .map((cell) => escapeCsvCell(cell))
        .join(','),
    )
  }
  return `${lines.join('\r\n')}\r\n`
}

/** 单行转成 JSON 对象；字段名用 snake_case，方便脚本直接消费 */
function toJsonItem(row: ExportTableRow) {
  return {
    weapon_id: row.weaponId,
    name: row.name,
    source: row.source,
    weapon_type: row.weaponTypeName || null,
    rarity: row.rarity,
    owned: row.owned,
    maxed: row.maxed,
    // 按语义槽位升序，3★ 武器就只有属性与技能两条
    traits: [...row.traits]
      .toSorted((a, b) => a.slot - b.slot)
      .map((trait) => ({
        slot: TRAIT_SLOT_KEYS[trait.slot] ?? String(trait.slot),
        name: trait.name,
        level: trait.level,
        max_level: trait.maxLevel,
      })),
    include_in_calculation: row.includeInCalculation,
    priority: row.priority,
    essence_count: row.essenceCount,
  }
}

/** 序列化成带元信息的 JSON 文本，缩进 2 空格便于直接阅读 */
export function exportRowsToJson(rows: readonly ExportTableRow[], meta: ExportTableMeta): string {
  const payload = {
    profile: meta.profile,
    exported_at: meta.exportedAt,
    count: rows.length,
    items: rows.map((row) => toJsonItem(row)),
  }
  return `${JSON.stringify(payload, null, 2)}\n`
}
