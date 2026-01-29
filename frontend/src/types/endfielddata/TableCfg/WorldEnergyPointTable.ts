import type { TranslationKey } from '@/types/common'

export interface WorldEnergyPoint {
  costStamina: number
  desc: TranslationKey
  enemyIds: string[]
  enemyLevels: number[]
  gameCategory: string
  gameGroupId: number
  gameMechanicsId: string
  gameName: TranslationKey
  levelId: string
  probGemItemIds: string[]
  recommendLv: number
  regularItemCount: never[]
  regularItemIds: never[]
  worldLevel: number
}

export type WorldEnergyPointTable = Record<string, WorldEnergyPoint>
