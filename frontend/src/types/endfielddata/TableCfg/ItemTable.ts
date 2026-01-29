import type { TranslationKey } from '@/types/common'

export interface Item {
  backpackCanDiscard: boolean
  decoDesc: TranslationKey
  desc: TranslationKey
  iconCompositeId: string
  iconId: string
  id: string
  maxBackpackStackCount: number
  maxStackCount: number
  modelKey: string
  name: TranslationKey
  noObtainWayConditionId: string[]
  noObtainWayHint: TranslationKey
  noObtainWayId: string[]
  obtainWayIds: string[]
  outcomeItemIds: string[]
  rarity: number
  showAllDepotCount: boolean
  showingType: number
  sortId1: number
  sortId2: number
  type: number
  valuableTabType: number
}

export type ItemTable = Record<string, Item>
