import { useStaticData } from '@/utils/gameData/staticData'

export interface EssenceStat {
  /** 自定义显示名称，用于武器总览页面展示 */
  name?: string
  attribute: string | null
  secondary: string | null
  skill: string | null
}

export function getEmptyStat(): EssenceStat {
  return {
    attribute: null,
    secondary: null,
    skill: null,
  }
}

export function getGemTagName(gemId: string): string {
  const { essencesMap } = useStaticData()
  const essence = essencesMap.value.get(gemId)
  if (essence === undefined) {
    return gemId
  }
  return essence.tagName
}

/**
 * 基础 / 附加属性的短名覆盖表：只收录通用规则算不出正确结果的词条。
 *
 * 其余词条交给 getStatShortName 的通用规则处理，游戏新增词条时无需维护此表。
 */
const STAT_SHORT_NAME_OVERRIDES: Record<string, string> = {
  gat_passive_attr_usp: '充能', // 终结技充能效率提升
}

/**
 * 技能词条的单字简称。
 *
 * 取首字还是取末字全看哪个字更有辨识度（「粉碎」取「碎」、「流转」取「流」），
 * 没有可靠的通用规则，因此逐条列出；十四个字互不相同，缩写后不会撞名。
 */
const SKILL_SHORT_NAMES: Record<string, string> = {
  gst_passive_break: '暴', // 残暴
  gst_passive_burst: '迸', // 迸发
  gst_passive_combo: '袭', // 追袭
  gst_passive_crit: '骨', // 切骨
  gst_passive_force: '攻', // 强攻
  gst_passive_heal: '疗', // 医疗
  gst_passive_keyword: '益', // 效益
  gst_passive_magabn: '术', // 附术
  gst_passive_phyabn: '巧', // 巧技
  gst_passive_smash: '碎', // 粉碎
  gst_passive_spirit: '昂', // 昂扬
  gst_passive_tacafter: '流', // 流转
  gst_passive_tactic: '压', // 压制
  gst_passive_ult: '夜', // 夜幕
}

/**
 * 取基础 / 附加属性词条的 2 字短名。
 *
 * 通用规则：去掉「提升」后缀，再去掉「伤害 / 效率」这类修饰后缀，最后截断到 2 个字。
 * 例：「敏捷提升」→「敏捷」、「灼热伤害提升」→「灼热」、「主能力提升」→「主能」。
 */
function getStatShortName(gemId: string): string {
  const override = STAT_SHORT_NAME_OVERRIDES[gemId]
  if (override !== undefined) {
    return override
  }
  return getGemTagName(gemId)
    .replace(/提升$/, '')
    .replace(/(?:伤害|效率)$/, '')
    .slice(0, 2)
}

/** 取技能词条的 1 字简称，表外的新词条退化为取首字。 */
function getSkillShortName(gemId: string): string {
  return SKILL_SHORT_NAMES[gemId] ?? getGemTagName(gemId).slice(0, 1)
}

export function getStatsForWeapon(weaponId: string): EssenceStat {
  const { weaponsMap } = useStaticData()
  const weapon = weaponsMap.value.get(weaponId)
  if (!weapon) {
    return getEmptyStat()
  }

  return {
    attribute: weapon.attributeStatId,
    secondary: weapon.secondaryStatId,
    skill: weapon.skillStatId,
  }
}

/**
 * 构造「属性组合」索引键。
 *
 * 内置武器（attributeStatId/secondaryStatId/skillStatId）与自定义基质
 * （attribute/secondary/skill）共用同一格式，两类条目才能互相匹配。
 */
export function buildStatKey(
  attribute: string | null,
  secondary: string | null,
  skill: string | null,
): string {
  return `${attribute}|${secondary}|${skill}`
}

/** 自定义基质配置类型 */
export interface CustomStat {
  /**
   * 稳定标识符，创建时生成后不再变化。
   *
   * 后端会为缺失该字段的旧配置补齐，因此运行时读到的条目一定带 ID。
   */
  id: string
  name?: string
  attribute: string | null
  secondary: string | null
  skill: string | null
  no_prompt_switch?: boolean
}

/** 自定义基质在 treasure_matrix 中的 weapon_id 前缀。 */
export const CUSTOM_ID_PREFIX = 'custom:'

/**
 * 旧格式前缀（`custom_stat_{下标}`）。
 *
 * 后端会在启动时把存量数据迁移为新格式，这里仅保留识别能力，
 * 使迁移完成前渲染出的界面不至于把旧条目错认成普通武器。
 */
const LEGACY_CUSTOM_ID_PREFIX = 'custom_stat_'

/** 生成一个新的自定义基质 ID。 */
export function createCustomStatId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID().replaceAll('-', '')
  }
  // 退化路径：仅用于不支持 crypto.randomUUID 的老环境
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`
}

/** 判断 weapon_id 是否指向自定义基质（兼容迁移前的旧格式）。 */
export function isCustomStatId(weaponId: string | null | undefined): boolean {
  if (!weaponId) return false
  return weaponId.startsWith(CUSTOM_ID_PREFIX) || weaponId.startsWith(LEGACY_CUSTOM_ID_PREFIX)
}

/** 由自定义基质构造其在 treasure_matrix 中的 weapon_id。 */
export function toCustomStatId(stat: Pick<CustomStat, 'id'>): string {
  return `${CUSTOM_ID_PREFIX}${stat.id}`
}

/**
 * 按 weapon_id 查找对应的自定义基质。
 *
 * 这是全前端唯一解析自定义基质 ID 的入口：新格式按 ID 查表，旧格式按下标
 * 兜底（仅在后端迁移生效前的极短窗口内可能出现）。
 *
 * @returns 命中的条目及其当前下标；未命中返回 null。
 */
export function findCustomStat(
  weaponId: string | null | undefined,
  customStats: readonly CustomStat[],
): { stat: CustomStat; index: number } | null {
  if (!weaponId) return null

  if (weaponId.startsWith(CUSTOM_ID_PREFIX)) {
    const id = weaponId.slice(CUSTOM_ID_PREFIX.length)
    const index = customStats.findIndex((stat) => stat.id === id)
    return index === -1 ? null : { stat: customStats[index]!, index }
  }

  if (weaponId.startsWith(LEGACY_CUSTOM_ID_PREFIX)) {
    const raw = weaponId.slice(LEGACY_CUSTOM_ID_PREFIX.length)
    if (!/^\d+$/.test(raw)) return null
    const index = Number.parseInt(raw, 10)
    const stat = customStats[index]
    return stat ? { stat, index } : null
  }

  return null
}

/** 自定义基质的兜底显示名（配置里没填名称时使用）。 */
export function fallbackCustomStatName(index: number): string {
  return `自定义基质 ${index + 1}`
}

/**
 * 生成「基础 × 附加 × 技能」的全部属性组合作为新的自定义基质。
 *
 * 已被占用的组合直接跳过，因此重复调用不会产生重复条目。
 *
 * @param attributeIds 基础属性词条 ID 列表
 * @param secondaryIds 附加属性词条 ID 列表
 * @param skillIds 技能属性词条 ID 列表
 * @param occupiedKeys 已被占用的属性组合键（由 buildStatKey 生成），命中的组合会被跳过
 * @returns 新建条目，每条都带稳定 ID 和「基础 2 字 + 附加 2 字 + 技能 1 字」的 5 字显示名
 */
export function buildFullCustomStatMatrix(
  attributeIds: readonly string[],
  secondaryIds: readonly string[],
  skillIds: readonly string[],
  occupiedKeys: ReadonlySet<string>,
): CustomStat[] {
  const generated: CustomStat[] = []
  for (const attribute of attributeIds) {
    for (const secondary of secondaryIds) {
      for (const skill of skillIds) {
        if (occupiedKeys.has(buildStatKey(attribute, secondary, skill))) {
          continue
        }
        generated.push({
          id: createCustomStatId(),
          name: `${getStatShortName(attribute)}${getStatShortName(secondary)}${getSkillShortName(skill)}`,
          attribute,
          secondary,
          skill,
        })
      }
    }
  }
  return generated
}

/**
 * 获取自定义基质的技能属性 ID
 * @param weaponId 自定义基质的 weapon_id
 * @param customStats 自定义基质配置列表
 * @returns 技能属性 ID，如果不存在则返回 null
 */
export function getCustomStatSkillId(
  weaponId: string,
  customStats: readonly CustomStat[],
): string | null {
  return findCustomStat(weaponId, customStats)?.stat.skill || null
}

/**
 * 获取自定义基质的名称
 * @param weaponId 自定义基质的 weapon_id
 * @param customStats 自定义基质配置列表
 * @returns 基质名称
 */
export function getCustomStatName(weaponId: string, customStats: readonly CustomStat[]): string {
  const found = findCustomStat(weaponId, customStats)
  if (!found) return '自定义基质'
  return found.stat.name || fallbackCustomStatName(found.index)
}
