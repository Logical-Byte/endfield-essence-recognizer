import { computed } from 'vue'
import {
  gemTable,
  gemTagIdTable,
  getTranslation,
  isLoaded,
  skillPatchTable,
  weaponBasicTable,
} from '@/utils/gameData/gameData'

export interface EssenceStat {
  attribute: string | null
  secondary: string | null
  skill: string | null
}

export function getEmptyStat(): EssenceStat {
  return {
    attribute: null,
    secondary: null,
    skill: null,
  }
}

export function getGemTagName(gemTermId: string): string {
  const gem = gemTable.value[gemTermId]
  if (gem === undefined) {
    return gemTermId
  }
  return getTranslation(gem.tagName) || gemTermId
}

export function getStatsForWeapon(weaponId: string): EssenceStat {
  const weapon = weaponBasicTable.value[weaponId]
  if (!weapon) {
    return getEmptyStat()
  }

  const result = getEmptyStat()
  for (const weaponSkill of weapon.weaponSkillList) {
    const skillPatch = skillPatchTable.value[weaponSkill]!
    const tagId = skillPatch.SkillPatchDataBundle[0]!.tagId
    const gemStat = gemTagIdTable.value[tagId]!
    const gem = gemTable.value[gemStat]!
    switch (gem.termType) {
      case 0: {
        result.attribute = gem.gemTermId
        break
      }
      case 1: {
        result.secondary = gem.gemTermId
        break
      }
      case 2: {
        result.skill = gem.gemTermId
        break
      }
    }
  }
  return result
}

export const statsForWeapon = computed(() => {
  if (!isLoaded.value) {
    return new Map<string, EssenceStat>()
  }
  const result: Map<string, EssenceStat> = new Map(
    Object.keys(weaponBasicTable.value).map((weaponId) => [weaponId, getStatsForWeapon(weaponId)]),
  )
  return result
})
