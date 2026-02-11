import type { ColorInstance } from 'color'
import type {
  EssenceInfo,
  EssenceListResponse,
  RarityColorResponse,
  WeaponInfo,
  WeaponListResponse,
  WeaponTypeInfo,
  WeaponTypeListResponse,
} from '@/types/staticData'
import Color from 'color'
import { computed, ref } from 'vue'

export const weaponsMap = ref<Map<string, WeaponInfo>>(new Map())
export const weaponTypes = ref<WeaponTypeInfo[]>([])
export const essencesMap = ref<Map<string, EssenceInfo>>(new Map())
export const rarityColors = ref<Record<number, string>>({})
export const isStaticDataLoaded = ref(false)

export const allAttributeStats = computed(() =>
  Array.from(essencesMap.value.values())
    .filter((e) => e.type === 'ATTRIBUTE')
    .map((e) => e.id),
)

export const allSecondaryStats = computed(() =>
  Array.from(essencesMap.value.values())
    .filter((e) => e.type === 'SECONDARY')
    .map((e) => e.id),
)

export const allSkillStats = computed(() =>
  Array.from(essencesMap.value.values())
    .filter((e) => e.type === 'SKILL')
    .map((e) => e.id),
)

export function getWeaponInfo(weaponId: string) {
  return weaponsMap.value.get(weaponId)
}

export function getWeaponName(weaponId: string) {
  return getWeaponInfo(weaponId)?.name ?? weaponId
}

export function getWeaponIconUrl(weaponId: string) {
  return getWeaponInfo(weaponId)?.icon_url ?? ''
}

export function getWeaponTierColor(weaponId: string): ColorInstance {
  const info = getWeaponInfo(weaponId)
  if (!info) return Color('#ffffff')
  const hex = rarityColors.value[info.rarity] || '#ffffff'
  return Color(hex)
}

export function getEssenceName(essenceId: string) {
  return essencesMap.value.get(essenceId)?.name ?? essenceId
}

export function getGemTagName(essenceId: string) {
  return essencesMap.value.get(essenceId)?.tag_name ?? essenceId
}

export async function initStaticData() {
  if (isStaticDataLoaded.value) return

  console.log('Initializing static data from API...')

  try {
    const [weaponsRes, typesRes, essencesRes, colorsRes] = await Promise.all([
      fetch('/api/static/weapons'),
      fetch('/api/static/weapon_types'),
      fetch('/api/static/essences'),
      fetch('/api/static/rarity_colors'),
    ])

    const weaponsData: WeaponListResponse = await weaponsRes.json()
    const typesData: WeaponTypeListResponse = await typesRes.json()
    const essencesData: EssenceListResponse = await essencesRes.json()
    const colorsData: RarityColorResponse = await colorsRes.json()

    weaponsMap.value = new Map(weaponsData.weapons.map((w) => [w.id, w]))
    weaponTypes.value = typesData.weapon_types
    essencesMap.value = new Map(essencesData.essences.map((e) => [e.id, e]))
    rarityColors.value = colorsData.colors

    isStaticDataLoaded.value = true
    console.log('Static data initialized.')
  } catch (error) {
    console.error('Failed to initialize static data:', error)
  }
}
