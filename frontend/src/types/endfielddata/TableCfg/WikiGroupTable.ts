import type { TranslationKey } from '@/types/common'

export interface WikiGroupEntry {
  groupId: string
  groupName: TranslationKey
  iconId: string
}

export interface WikiCategory {
  list: WikiGroupEntry[]
}

export type WikiGroupTable = Record<string, WikiCategory>
