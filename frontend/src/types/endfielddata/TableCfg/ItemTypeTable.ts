import type { TranslationKey } from '@/types/common'

export interface ItemType {
  barkWhenGot: boolean
  bgType: number
  hideItemInBagToast: boolean
  hideNewToast: boolean
  itemType: number
  name: TranslationKey
  showCount: boolean
  showCountInTips: boolean
  storageSpace: number
  unlockSystemType: number
  valuableTabType: number
}

export type ItemTypeTable = Record<string, ItemType>
