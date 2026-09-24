import type { ColorInstance } from 'color'
import Color from 'color'
import { useStaticData } from '@/utils/gameData/staticData'

export function getItemName(itemId: string): string {
  const { weaponsMap, essencesMap } = useStaticData()
  const weapon = weaponsMap.value.get(itemId)
  if (weapon) return weapon.name
  const essence = essencesMap.value.get(itemId)
  if (essence) return essence.name
  return itemId
}

export function getItemIconUrl(itemId: string): string | undefined {
  const { weaponsMap } = useStaticData()
  const weapon = weaponsMap.value.get(itemId)
  if (weapon) return weapon.iconUrl
  return undefined
}

export function getItemRarity(itemId: string): number | undefined {
  const { weaponsMap } = useStaticData()
  return weaponsMap.value.get(itemId)?.rarity
}

export function getItemTierColor(itemId: string): ColorInstance {
  const { rarityColors } = useStaticData()
  const rarity = getItemRarity(itemId)
  if (rarity !== undefined && rarityColors.value[rarity] !== undefined) {
    return Color(rarityColors.value[rarity])
  }
  return Color('transparent') // Default to transparent if rarity is undefined or not found
}
