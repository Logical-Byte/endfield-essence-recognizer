import type { TranslationKey } from '@/types/common'

export interface WikiEntry {
  desc: TranslationKey
  groupId: string
  id: string
  order: number
  prtsId: string
  refItemId: string
  refMonsterTemplateId: string
}

export type WikiEntryDataTable = Record<string, WikiEntry>
