export interface WeaponInfo {
  id: string
  name: string
  iconUrl: string
  rarity: number
  attributeEssenceId: string | null
  secondaryEssenceId: string | null
  skillEssenceId: string | null
}

export interface WeaponTypeInfo {
  id: string
  name: string
  iconUrl: string
  weaponIds: string[]
  sortOrder: number
}

export interface EssenceInfo {
  id: string
  name: string
  tagName: string
  type: 'ATTRIBUTE' | 'SECONDARY' | 'SKILL'
}

export interface WeaponListResponse {
  weapons: WeaponInfo[]
}

export interface WeaponTypeListResponse {
  weaponTypes: WeaponTypeInfo[]
}

export interface EssenceListResponse {
  essences: EssenceInfo[]
}

export interface RarityColorResponse {
  colors: Record<number, string>
}

export interface StaticDataState {
  weaponsMap: Map<string, WeaponInfo>
  weaponTypes: WeaponTypeInfo[]
  essencesMap: Map<string, EssenceInfo>
  rarityColors: Record<number, string>
  isLoaded: boolean
}
