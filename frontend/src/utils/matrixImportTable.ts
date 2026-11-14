/**
 * 宝藏基质导入表格的解析与合并规划。
 *
 * 与 matrixExportTable.ts 互为反操作：那边把卡片写成本文，这里把它读回条目，
 * 并算出「合并 / 替换」之后要提交给后端的整表。解析与合并都不碰应用状态，
 * 输入是普通字符串与数组，所以能在 node 环境的单测里直接跑。
 *
 * 三条安全约定：
 * - 文件里「未获得」的行不导入：否则一次导入会把全部武器标成已拥有；
 * - 一行等级都读不出来的行直接跳过：猜出来的默认等级会把现有配置洗成 1；
 * - 未知武器、缺失的自定义基质一律跳过并计数，由 UI 报给用户，不静默吞掉。
 */

import type { TreasureMatrixEntry } from '@/composables/useProfiles'

/** 各槽位满级，与后端 schemas/profile.py 的 le 约束一致 */
const MAX_LEVELS = [6, 6, 3] as const

/** 优先级上限，与 `/api/profiles/weapon_priority` 的 le=9 一致 */
const MAX_PRIORITY = 9

/** 自定义基质在矩阵里的 weapon_id 前缀，与后端 CUSTOM_ID_PREFIX 一致 */
const CUSTOM_ID_PREFIX = 'custom:'

/** 解析阶段的结构常量，与导出 CSV 的表头一一对应 */
const HEADER_WEAPON_ID = '武器ID'
const HEADER_NAME = '名称'
const HEADER_OWNED = '是否已获得'
const HEADER_CALCULATION = '参与计算'
const HEADER_PRIORITY = '优先级'
const HEADER_LEVELS = ['属性等级', '附加等级', '技能等级'] as const

/** 行被跳过的原因 */
export type ImportSkipReason =
  /** 缺 weapon_id 或等级一列都读不出来 */
  | 'invalid_row'
  /** 等级越界或不是整数 */
  | 'invalid_level'
  /** 文件里标记为未获得，不导入 */
  | 'not_owned'
  /** 内置武器 ID 不在当前静态数据里 */
  | 'unknown_weapon'
  /** 引用了本机不存在的自定义基质 */
  | 'missing_custom'

export interface ImportSkip {
  /** 1 起的行号：CSV 指数据行（表头算第 1 行），JSON 指 items 下标 + 1 */
  lineNumber: number
  weaponId: string
  reason: ImportSkipReason
}

/** 解析出来的一行，尚未与当前配置合并 */
export interface ImportRow {
  lineNumber: number
  weaponId: string
  /** 文件里记录的显示名，仅作参考；内置武器最终以静态数据为准 */
  name: string
  /** 各槽位等级；null 表示文件里没有该槽位（3★ 武器没有附加词条） */
  levels: readonly [number | null, number | null, number | null]
  /** 是否已获得；null 表示文件没写（按已获得处理） */
  owned: boolean | null
  /** 是否参与计算；null 表示文件没写，合并时沿用现有值 */
  includeInCalculation: boolean | null
  /** 优先级；null 表示文件没写，合并时沿用现有值 */
  priority: number | null
}

export interface ParsedImport {
  rows: ImportRow[]
  skipped: ImportSkip[]
}

/** 合并：按 weapon_id 覆盖，文件外的条目保留；替换：整表以文件为准 */
export type ImportMode = 'merge' | 'replace'

export interface ImportPlanInput {
  rows: readonly ImportRow[]
  skipped: readonly ImportSkip[]
  existing: readonly TreasureMatrixEntry[]
  /** 内置武器：weapon_id → 规范显示名 */
  builtinNames: ReadonlyMap<string, string>
  /** 本机存在的自定义基质：带 custom: 前缀的 weapon_id → 显示名 */
  customNames: ReadonlyMap<string, string>
  /**
   * 目标账号的独立优先级偏好（含未拥有基质的武器）。
   *
   * `treasure_matrix` 里的 priority 只是这份偏好的投影，覆盖不到「没配基质
   * 但手设过优先级」的武器；缺了它就可能在导入时把这类偏好清零。
   */
  weaponPriorities: Readonly<Record<string, number>>
  mode: ImportMode
}

export interface ImportPlan {
  /** 最终提交给后端的整表 */
  entries: TreasureMatrixEntry[]
  /** 文件里新增的条目 */
  added: TreasureMatrixEntry[]
  /** 文件里覆盖掉的条目 */
  updated: TreasureMatrixEntry[]
  /** 仅替换模式有：现有条目里不在文件中的，将被删除 */
  removed: TreasureMatrixEntry[]
  /** 被跳过的行（含解析阶段就跳过的） */
  skipped: ImportSkip[]
}

/** 去掉 UTF-8 BOM 与首尾空白：Excel 另存的 CSV 通常带 BOM */
function stripBom(text: string): string {
  return text.replace(/^\uFEFF/, '')
}

/** 一条 CSV 记录：单元格 + 它在文件里的**物理**起始行号（1 起） */
interface CsvRecord {
  cells: string[]
  line: number
}

/**
 * 切分 CSV 为记录列表。
 *
 * 只实现导入需要的最小集：双引号包裹、"" 转义、CRLF/LF 行尾、字段内换行。
 * 不引第三方 CSV 依赖——只为读回自己导出的文件，不值得为它增加一个依赖。
 *
 * 行号按物理行统计（引号内的换行也计数），跳过问题的报告才能对得上用户
 * 在编辑器里看到的行号；按记录下标推算会在有空白行或字段内换行时错位。
 */
function splitCsvRecords(text: string): CsvRecord[] {
  const records: CsvRecord[] = []
  let cells: string[] = []
  let cell = ''
  let quoted = false
  let currentLine = 1
  let recordLine = 1

  for (let index = 0; index < text.length; index++) {
    const char = text[index]!
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') {
          cell += '"'
          index++
        } else {
          quoted = false
        }
      } else {
        if (char === '\n') currentLine++
        cell += char
      }
      continue
    }
    if (char === '"') {
      quoted = true
      continue
    }
    if (char === ',') {
      cells.push(cell)
      cell = ''
      continue
    }
    if (char === '\r') continue
    if (char === '\n') {
      cells.push(cell)
      records.push({ cells, line: recordLine })
      cells = []
      cell = ''
      currentLine++
      recordLine = currentLine
      continue
    }
    cell += char
  }

  if (cell !== '' || cells.length > 0) {
    cells.push(cell)
    records.push({ cells, line: recordLine })
  }
  return records
}

/** 「是/否」表头的布尔解析；空值表示文件没写 */
function parseFlag(raw: string | undefined): boolean | null {
  const text = (raw ?? '').trim().toLowerCase()
  if (text === '') return null
  if (text === '是' || text === 'true' || text === '1') return true
  if (text === '否' || text === 'false' || text === '0') return false
  return null
}

/** 等级解析：空 → null；越界或非整数 → 'invalid' */
function parseLevel(raw: string | undefined, maxLevel: number): number | null | 'invalid' {
  const text = (raw ?? '').trim()
  if (text === '') return null
  if (!/^\d+$/.test(text)) return 'invalid'
  const value = Number(text)
  return value < 1 || value > maxLevel ? 'invalid' : value
}

/**
 * 优先级解析：非法值按「未设置」处理，不值得因此丢掉整行等级数据。
 *
 * 上限 9 与 `/api/profiles/weapon_priority` 的 le=9 和界面上的优先级控件
 * 对齐：超过 9 的值无法在界面上修改，只会在交换判定里造成反直觉的排序，
 * 因此按「未设置」处理而不是原样写入。
 */
function parsePriority(raw: string | undefined): number | null {
  const text = (raw ?? '').trim()
  if (!/^\d+$/.test(text)) return null
  const value = Number(text)
  return value > MAX_PRIORITY ? null : value
}

/** 按表头名定位列，缺列时返回 undefined——列顺序变了也不会错位 */
function columnIndex(header: readonly string[], name: string): number | undefined {
  const index = header.findIndex((cell) => cell.trim() === name)
  return index === -1 ? undefined : index
}

function cellAt(cells: readonly string[], index: number | undefined): string | undefined {
  return index === undefined ? undefined : cells[index]
}

function parseCsv(text: string): ParsedImport {
  // 空白行不参与解析，但仍占物理行：行号必须来自记录本身而不是过滤后的下标
  const records = splitCsvRecords(text).filter((record) =>
    record.cells.some((cell) => cell.trim() !== ''),
  )
  const headerRecord = records.shift()
  if (!headerRecord) return { rows: [], skipped: [] }
  const header = headerRecord.cells

  const weaponIdColumn = columnIndex(header, HEADER_WEAPON_ID)
  if (weaponIdColumn === undefined) {
    throw new Error(`CSV 缺少「${HEADER_WEAPON_ID}」列，无法确定要导入哪把武器`)
  }

  const nameColumn = columnIndex(header, HEADER_NAME)
  const ownedColumn = columnIndex(header, HEADER_OWNED)
  const calculationColumn = columnIndex(header, HEADER_CALCULATION)
  const priorityColumn = columnIndex(header, HEADER_PRIORITY)
  const levelColumns = HEADER_LEVELS.map((name) => columnIndex(header, name))

  const parsed: ParsedImport = { rows: [], skipped: [] }

  for (const { cells, line: lineNumber } of records) {
    const weaponId = (cellAt(cells, weaponIdColumn) ?? '').trim()
    if (!weaponId) {
      parsed.skipped.push({ lineNumber, weaponId: '', reason: 'invalid_row' })
      continue
    }

    const owned = parseFlag(cellAt(cells, ownedColumn))
    if (owned === false) {
      parsed.skipped.push({ lineNumber, weaponId, reason: 'not_owned' })
      continue
    }

    const levels: [number | null, number | null, number | null] = [null, null, null]
    let levelInvalid = false
    for (const [slot, column] of levelColumns.entries()) {
      const value = parseLevel(cellAt(cells, column), MAX_LEVELS[slot]!)
      if (value === 'invalid') {
        levelInvalid = true
        break
      }
      levels[slot] = value
    }

    if (levelInvalid) {
      parsed.skipped.push({ lineNumber, weaponId, reason: 'invalid_level' })
      continue
    }
    if (levels.every((level) => level === null)) {
      parsed.skipped.push({ lineNumber, weaponId, reason: 'invalid_row' })
      continue
    }

    parsed.rows.push({
      lineNumber,
      weaponId,
      name: (cellAt(cells, nameColumn) ?? '').trim(),
      levels,
      owned,
      includeInCalculation: parseFlag(cellAt(cells, calculationColumn)),
      priority: parsePriority(cellAt(cells, priorityColumn)),
    })
  }

  return parsed
}

/** 槽位解析：接受 0/1/2、attribute/secondary/skill 以及中文槽位名 */
function toSlotIndex(raw: unknown): number | null {
  if (typeof raw === 'number') {
    return Number.isInteger(raw) && raw >= 0 && raw <= 2 ? raw : null
  }
  if (typeof raw === 'string') {
    const text = raw.trim().toLowerCase()
    if (text === 'attribute' || text === '属性') return 0
    if (text === 'secondary' || text === '附加') return 1
    if (text === 'skill' || text === '技能') return 2
  }
  return null
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null
}

function parseJsonItem(
  item: unknown,
  lineNumber: number,
): { row: ImportRow } | { skip: ImportSkip } {
  const record = asRecord(item)
  if (!record) {
    return { skip: { lineNumber, weaponId: '', reason: 'invalid_row' } }
  }

  const weaponId = typeof record.weapon_id === 'string' ? record.weapon_id.trim() : ''
  if (!weaponId) {
    return { skip: { lineNumber, weaponId: '', reason: 'invalid_row' } }
  }

  const owned = typeof record.owned === 'boolean' ? record.owned : null
  if (owned === false) {
    return { skip: { lineNumber, weaponId, reason: 'not_owned' } }
  }

  const levels: [number | null, number | null, number | null] = [null, null, null]
  const traits = Array.isArray(record.traits) ? record.traits : []
  for (const trait of traits) {
    const traitRecord = asRecord(trait)
    if (!traitRecord) continue
    const slot = toSlotIndex(traitRecord.slot)
    if (slot === null) continue
    const level = traitRecord.level
    if (
      typeof level !== 'number' ||
      !Number.isInteger(level) ||
      level < 1 ||
      level > MAX_LEVELS[slot]!
    ) {
      return { skip: { lineNumber, weaponId, reason: 'invalid_level' } }
    }
    levels[slot] = level
  }

  if (levels.every((level) => level === null)) {
    return { skip: { lineNumber, weaponId, reason: 'invalid_row' } }
  }

  const priority = record.priority
  return {
    row: {
      lineNumber,
      weaponId,
      name: typeof record.name === 'string' ? record.name.trim() : '',
      levels,
      owned,
      includeInCalculation:
        typeof record.include_in_calculation === 'boolean' ? record.include_in_calculation : null,
      priority:
        typeof priority === 'number' && Number.isInteger(priority) && priority >= 0
          ? priority
          : null,
    },
  }
}

function parseJson(text: string): ParsedImport {
  let payload: unknown
  try {
    payload = JSON.parse(text)
  } catch (error) {
    throw new Error(`JSON 解析失败：${error instanceof Error ? error.message : String(error)}`)
  }

  const container = asRecord(payload)
  const items = Array.isArray(payload) ? payload : (container?.items ?? null)
  if (!Array.isArray(items)) {
    throw new TypeError('JSON 里找不到 items 数组，这不是宝藏基质导出文件')
  }

  const parsed: ParsedImport = { rows: [], skipped: [] }
  for (const [index, item] of items.entries()) {
    const result = parseJsonItem(item, index + 1)
    if ('skip' in result) parsed.skipped.push(result.skip)
    else parsed.rows.push(result.row)
  }
  return parsed
}

/**
 * 解析导入文本，按内容而不是扩展名判断格式。
 *
 * 用户把 JSON 存成 .csv（或反过来）是常事，内容嗅探比看文件名可靠：
 * 以 `{` 或 `[` 开头就是 JSON，其余按 CSV 处理。
 *
 * @throws Error 结构性问题（不是 JSON、缺武器ID列、找不到 items）时抛出，
 *   消息直接面向用户展示；行级问题走 skipped 返回，不中断整批。
 */
export function parseImportText(text: string): ParsedImport {
  const trimmed = stripBom(text).trimStart()
  if (trimmed === '') throw new Error('文件是空的')
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) return parseJson(trimmed)
  return parseCsv(trimmed)
}

/**
 * 合并解析结果与现有配置，算出最终要提交的整表。
 *
 * 缺省值一律「沿用目标账号现值，再退回默认值」：
 * - 等级：文件缺该槽位时保留原条目的等级，不能拿 1 覆盖已有进度；
 * - 参与计算：文件没写时沿用原值；
 * - 优先级：文件没写**或写 0** 时都沿用目标账号现值。0 在导出里表示
 *   「未设置」，若把它当成「清零」指令，导入一份旧文件就会把用户手设的
 *   优先级连同「未拥有但设过优先级」的独立偏好一起抹掉。代价是导入无法
 *   清除优先级，但优先级可以在界面上单独改，不值得为一个低频操作牺牲安全。
 */
export function buildImportPlan(input: ImportPlanInput): ImportPlan {
  const existingById = new Map(input.existing.map((entry) => [entry.weapon_id, entry] as const))
  const skipped = [...input.skipped]

  // 同一把武器在文件里出现多次时以最后一行为准，避免提交出重复条目
  const incoming = new Map<string, TreasureMatrixEntry>()
  for (const row of input.rows) {
    const name = input.builtinNames.get(row.weaponId) ?? input.customNames.get(row.weaponId)
    if (name === undefined) {
      skipped.push({
        lineNumber: row.lineNumber,
        weaponId: row.weaponId,
        reason: row.weaponId.startsWith(CUSTOM_ID_PREFIX) ? 'missing_custom' : 'unknown_weapon',
      })
      continue
    }

    const previous = existingById.get(row.weaponId)
    // 目标账号的独立优先级偏好：矩阵里没有该武器时它只存在于 weapon_priorities
    const savedPriority = input.weaponPriorities[row.weaponId]
    const explicitPriority = row.priority !== null && row.priority > 0 ? row.priority : null

    incoming.set(row.weaponId, {
      weapon_id: row.weaponId,
      weapon_name: name,
      affix1_level: row.levels[0] ?? previous?.affix1_level ?? 1,
      affix2_level: row.levels[1] ?? previous?.affix2_level ?? 1,
      affix3_level: row.levels[2] ?? previous?.affix3_level ?? 1,
      include_in_calculation: row.includeInCalculation ?? previous?.include_in_calculation ?? true,
      priority: explicitPriority ?? previous?.priority ?? savedPriority ?? 0,
    })
  }

  const added = [...incoming.values()].filter((entry) => !existingById.has(entry.weapon_id))
  const updated = [...incoming.values()].filter((entry) => existingById.has(entry.weapon_id))

  if (input.mode === 'merge') {
    const replaced = new Map(incoming)
    const entries = input.existing.map((entry) => replaced.get(entry.weapon_id) ?? { ...entry })
    entries.push(...added)
    return { entries, added, updated, removed: [], skipped }
  }

  const keptIds = new Set(incoming.keys())
  return {
    entries: [...incoming.values()],
    added,
    updated,
    removed: input.existing.filter((entry) => !keptIds.has(entry.weapon_id)),
    skipped,
  }
}

/**
 * 这份导入计划是否值得提交。
 *
 * 合并模式下空文件等于什么都没做，应禁用；替换模式下只要会删掉现有条目
 * 就仍然有意义——用一份空文件清空账号，正是「恢复空白配置」的正常路径。
 */
export function canApplyPlan(plan: ImportPlan, mode: ImportMode): boolean {
  if (plan.added.length + plan.updated.length > 0) return true
  return mode === 'replace' && plan.removed.length > 0
}

/**
 * 把账号当前的矩阵写成可再次导入的 JSON 快照。
 *
 * 用导入格式而不是原始 dump：回滚时直接把这份文件按「替换」模式导回去即可，
 * 不需要另写一套恢复逻辑。`owned` 恒为 true——矩阵里的条目本来就代表已拥有。
 *
 * @param profile 账号名称
 * @param entries 该账号当前的宝藏基质条目
 * @param exportedAt ISO 8601 时间戳
 * @returns JSON 文本（带缩进，末尾换行）
 */
export function entriesToBackupJson(
  profile: string,
  entries: readonly TreasureMatrixEntry[],
  exportedAt: string,
): string {
  const payload = {
    profile,
    exported_at: exportedAt,
    count: entries.length,
    items: entries.map((entry) => ({
      weapon_id: entry.weapon_id,
      name: entry.weapon_name,
      owned: true,
      include_in_calculation: entry.include_in_calculation ?? true,
      priority: entry.priority ?? 0,
      traits: [
        { slot: 'attribute', level: entry.affix1_level },
        { slot: 'secondary', level: entry.affix2_level },
        { slot: 'skill', level: entry.affix3_level },
      ],
    })),
  }
  return `${JSON.stringify(payload, null, 2)}\n`
}
