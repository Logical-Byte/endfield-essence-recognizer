import type {
  EssenceInfo,
  EssenceListResponse,
  RarityColorResponse,
  WeaponInfo,
  WeaponListResponse,
  WeaponTypeInfo,
  WeaponTypeListResponse,
} from '@/types/staticData'
import { ref, watch } from 'vue'
import { useLanguage } from '@/composables/useLanguage'

const weaponsMap = ref<Map<string, WeaponInfo>>(new Map())
const weaponTypes = ref<WeaponTypeInfo[]>([])
const essencesMap = ref<Map<string, EssenceInfo>>(new Map())
const rarityColors = ref<Record<number, string>>({})
const isLoaded = ref(false)

async function fetchStaticData() {
  try {
    const [weaponsRes, weaponTypesRes, essencesRes, rarityColorsRes] = await Promise.all([
      fetch(`/api/static/weapons`).then((res) => res.json() as Promise<WeaponListResponse>),
      fetch(`/api/static/weapon_types`).then(
        (res) => res.json() as Promise<WeaponTypeListResponse>,
      ),
      fetch(`/api/static/essences`).then(
        (res) => res.json() as Promise<EssenceListResponse>,
      ),
      fetch(`/api/static/rarity_colors`).then((res) => res.json() as Promise<RarityColorResponse>),
    ])

    weaponsMap.value = new Map(weaponsRes.weapons.map((w) => [w.id, w]))
    weaponTypes.value = weaponTypesRes.weaponTypes
    essencesMap.value = new Map(essencesRes.essences.map((e) => [e.id, e]))
    rarityColors.value = rarityColorsRes.colors
    isLoaded.value = true
  } catch (error) {
    console.error('Failed to fetch static data:', error)
  }
}

export function useStaticData() {
  return {
    weaponsMap,
    weaponTypes,
    essencesMap,
    rarityColors,
    isLoaded,
    fetchStaticData,
  }
}
