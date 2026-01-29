import type { TranslationKey } from '@/types/common'

export interface BlackboardEntry {
  key: string
  value: number
  valueStr: string
}

export interface SkillPatchTableItem {
  blackboard: BlackboardEntry[]
  coolDown: number
  costType: number
  costValue: number
  description: TranslationKey
  iconBgType: number
  iconId: string
  level: number
  maxChargeTime: number
  skillId: string
  skillName: TranslationKey
  subDescList: string[]
  subDescNameList: TranslationKey[]
  tagId: string
}

export interface SkillPatchDataBundle {
  SkillPatchDataBundle: SkillPatchTableItem[]
}

export type SkillPatchTable = Record<string, SkillPatchDataBundle>
