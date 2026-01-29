import type { TranslationKey } from '@/types/common'

interface Gem {
  gemTermId: string
  isSkillTerm: boolean
  sortOrder: number
  tagDesc: TranslationKey
  tagIcon: string
  tagId: string
  tagName: TranslationKey
  termType: number
}

export type GemTable = Record<string, Gem>
