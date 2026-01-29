import { getTranslation, itemTable, rarityColorTable } from '@/utils/gameData/gameData'
import type { ColorInstance } from 'color'
import Color from 'color'

export function getItemName(itemId: string, language?: string): string {
  if (itemTable.value[itemId] === undefined) {
    return itemId
  }
  return getTranslation(itemTable.value[itemId].name, language)
}

export function getItemIconUrl(itemId: string): string | undefined {
  const iconId = itemTable.value[itemId]?.iconId
  if (iconId === undefined) {
    return undefined
  }
  return `https://cos.yituliu.cn/endfield/unpack-images/items/${iconId}.webp`
}

export function getItemRarity(itemId: string): number | undefined {
  return itemTable.value[itemId]?.rarity ?? undefined
}

export function getItemTierColor(itemId: string): ColorInstance {
  const rarity = getItemRarity(itemId)
  if (rarity !== undefined && rarityColorTable.value[rarity] !== undefined) {
    return Color(rarityColorTable.value[rarity].color)
  }
  return Color('transparent') // Default to transparent if rarity is undefined or not found
}
