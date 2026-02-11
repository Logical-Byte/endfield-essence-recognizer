export interface WeaponInfo {
  id: string
  name: string
  icon_url: string
  rarity: number
  attribute_essence_id: string | null
  secondary_essence_id: string | null
  skill_essence_id: string | null
}

export interface WeaponTypeInfo {
  id: string
  name: string
  icon_url: string
  sort_order: number
  weapon_ids: string[]
}

export type EssenceType = 'ATTRIBUTE' | 'SECONDARY' | 'SKILL'

export interface EssenceInfo {
  id: string
  name: string
  tag_name: string
  type: EssenceType
}

export interface WeaponListResponse {
  weapons: WeaponInfo[]
}

export interface WeaponTypeListResponse {
  weapon_types: WeaponTypeInfo[]
}

export interface EssenceListResponse {
  essences: EssenceInfo[]
}

export interface RarityColorResponse {
  colors: Record<number, string>
}
