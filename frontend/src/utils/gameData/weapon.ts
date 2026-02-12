import { useStaticData } from '@/utils/gameData/staticData'

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

export function getGemTagName(gemId: string): string {
  const { essencesMap } = useStaticData()
  const essence = essencesMap.value.get(gemId)
  if (essence === undefined) {
    return gemId
  }
  return essence.tagName
}

export function getStatsForWeapon(weaponId: string): EssenceStat {
  const { weaponsMap } = useStaticData()
  const weapon = weaponsMap.value.get(weaponId)
  if (!weapon) {
    return getEmptyStat()
  }

  return {
    attribute: weapon.attributeEssenceId,
    secondary: weapon.secondaryEssenceId,
    skill: weapon.skillEssenceId,
  }
}
