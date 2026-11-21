/**
 * 自定义能量淤积点（刷取地点）标识工具。
 *
 * 自定义条目落盘在后端的 `custom_alluviums.json`，全账号通用；各账号的刷取
 * 地点筛选以 `custom_alluvium:{id}` 为键保存勾选状态，因此这里的前缀必须与
 * 后端 `CUSTOM_ALLUVIUM_ID_PREFIX` 保持一致。
 */

/** 自定义能量淤积点配置类型（与后端 schemas/custom_alluvium.py 对应） */
export interface CustomAlluvium {
  /** 稳定标识符，创建时生成后不再变化；空串表示后端尚未分配 */
  id: string
  /** 显示名称；为空时使用兜底名 */
  name?: string
  /** 可刷出的基础属性词条 ID；为空表示不限制 */
  attribute_stats?: string[]
  /** 可刷出的附加属性词条 ID */
  secondary_stats?: string[]
  /** 可刷出的技能属性词条 ID */
  skill_stats?: string[]
}

/** 自定义淤积点在刷取地点筛选配置中的 key 前缀，与后端一致。 */
export const CUSTOM_ALLUVIUM_ID_PREFIX = 'custom_alluvium:'

/** 生成一个新的自定义淤积点 ID。 */
export function createCustomAlluviumId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID().replaceAll('-', '')
  }
  // 退化路径：仅用于不支持 crypto.randomUUID 的老环境
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`
}

/** 判断 battleId 是否指向自定义淤积点。 */
export function isCustomAlluviumId(battleId: string | null | undefined): boolean {
  if (!battleId) return false
  return battleId.startsWith(CUSTOM_ALLUVIUM_ID_PREFIX)
}

/** 由自定义淤积点构造其在刷取地点筛选配置中的 battleId。 */
export function toCustomAlluviumId(alluvium: Pick<CustomAlluvium, 'id'>): string {
  return `${CUSTOM_ALLUVIUM_ID_PREFIX}${alluvium.id}`
}

/** 自定义淤积点的兜底显示名（配置里没填名称时使用）。 */
export function fallbackCustomAlluviumName(index: number): string {
  return `自定义淤积点 ${index + 1}`
}

/**
 * 判断某个地点的基础属性池是否覆盖指定基础属性。
 *
 * 池为空表示「不限制」（内置地点就是这样）；池非空时只有池里有的基础属性才能
 * 在该地点刷出来，池外的武器即使附加 / 技能对得上也刷不到。
 */
export function alluviumAllowsAttribute(
  attributeStats: readonly string[],
  attribute: string,
): boolean {
  return attributeStats.length === 0 || attributeStats.includes(attribute)
}
