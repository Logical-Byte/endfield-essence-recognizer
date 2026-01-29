import type { TranslationKey } from '@/types/common'

export interface WeaponBasic {
  breakthroughTemplateId: string
  engName: TranslationKey
  levelTemplateId: string
  maxLv: number
  modelPath: string
  potentialUpItemList: string[]
  rarity: number
  talentTemplateId: string
  weaponDesc: TranslationKey
  weaponId: string
  weaponPotentialSkill: string
  weaponSkillList: string[]
  weaponType: number
}

export type WeaponBasicTable = Record<string, WeaponBasic>
