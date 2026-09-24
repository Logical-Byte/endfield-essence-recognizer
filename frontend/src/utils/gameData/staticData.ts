import type {
  EnergyAlluviumInfo,
  EnergyAlluviumListResponse,
  EssenceInfo,
  EssenceListResponse,
  MatrixIconResponse,
  RarityColorResponse,
  WeaponInfo,
  WeaponListResponse,
  WeaponTypeInfo,
  WeaponTypeListResponse,
} from '@/types/staticData'
import { ref } from 'vue'
import { useToast } from '@/composables/useToast'

const weaponsMap = ref<Map<string, WeaponInfo>>(new Map())
const weaponTypes = ref<WeaponTypeInfo[]>([])
const essencesMap = ref<Map<string, EssenceInfo>>(new Map())
const rarityColors = ref<Record<number, string>>({})
const matrixIcons = ref<MatrixIconResponse>({ essenceBg: '', defaultIcon: '', skills: {} })
const energyAlluviums = ref<EnergyAlluviumInfo[]>([])
const isLoaded = ref(false)

/**
 * 辅助函数：检查 HTTP 响应状态码并解析 JSON
 */
async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText} (${url})`)
  }
  return res.json() as Promise<T>
}

/** 拉取可降级的装饰性数据：失败只记录，不影响核心数据可用性 */
async function fetchOptionalJson<T>(url: string, fallback: T): Promise<T> {
  try {
    return await fetchJson<T>(url)
  } catch (error) {
    console.warn(`可选静态数据加载失败，已降级：${url}`, error)
    return fallback
  }
}

async function fetchStaticData() {
  try {
    // 核心数据缺任意一项都无法正常工作，整体失败；
    // 图标之类的装饰性资源单独降级，不能让它们拖垮整个应用。
    const [weaponsRes, weaponTypesRes, essencesRes, rarityColorsRes, alluviumsRes, matrixIconsRes] =
      await Promise.all([
        fetchJson<WeaponListResponse>(`/api/static/weapons`),
        fetchJson<WeaponTypeListResponse>(`/api/static/weapon_types`),
        fetchJson<EssenceListResponse>(`/api/static/essences`),
        fetchJson<RarityColorResponse>(`/api/static/rarity_colors`),
        fetchJson<EnergyAlluviumListResponse>(`/api/static/energy_alluviums`),
        fetchOptionalJson<MatrixIconResponse>(`/api/static/matrix_icons`, {
          essenceBg: '',
          defaultIcon: '',
          skills: {},
        }),
      ])

    weaponsMap.value = new Map(weaponsRes.weapons.map((w) => [w.id, w]))
    weaponTypes.value = weaponTypesRes.weaponTypes
    essencesMap.value = new Map(essencesRes.items.map((e) => [e.id, e]))
    rarityColors.value = rarityColorsRes.colors
    matrixIcons.value = matrixIconsRes
    energyAlluviums.value = alluviumsRes.items
    isLoaded.value = true
  } catch (error) {
    console.error('Failed to fetch static data:', error)
    // 静态数据是全站的基础，加载失败必须让用户知道，
    // 否则界面只是空空如也，看不出是出错还是真的没数据。
    useToast().error(
      `游戏数据加载失败，请检查后端服务是否正常：${
        error instanceof Error ? error.message : String(error)
      }`,
      10_000,
    )
  }
}

export function useStaticData() {
  return {
    weaponsMap,
    weaponTypes,
    essencesMap,
    rarityColors,
    matrixIcons,
    energyAlluviums,
    isLoaded,
    fetchStaticData,
  }
}
