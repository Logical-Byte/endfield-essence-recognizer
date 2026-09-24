export interface WeaponInfo {
  id: string
  name: string
  iconUrl: string
  rarity: number
  attributeStatId: string | null
  secondaryStatId: string | null
  skillStatId: string | null
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
  items: EssenceInfo[]
}

export interface RarityColorResponse {
  colors: Record<number, string>
}

export interface MatrixIconResponse {
  essenceBg: string
  defaultIcon: string
  skills: Record<string, string>
}

export interface EnergyAlluviumInfo {
  battleId: string
  battleName: string
  imageUrl?: string
  secondaryStats: string[]
  skillStats: string[]
}

export interface EnergyAlluviumListResponse {
  items: EnergyAlluviumInfo[]
}

export interface StaticDataState {
  weaponsMap: Map<string, WeaponInfo>
  weaponTypes: WeaponTypeInfo[]
  essencesMap: Map<string, EssenceInfo>
  rarityColors: Record<number, string>
  matrixIcons: MatrixIconResponse
  energyAlluviums: EnergyAlluviumInfo[]
  isLoaded: boolean
}
