import type { TranslationKey } from '@/types/common'
import type { GemTable } from '@/types/endfielddata/TableCfg/GemTable'
import type { GemTagIdTable } from '@/types/endfielddata/TableCfg/GemTagIdTable'
import type { I18nTextTable } from '@/types/endfielddata/TableCfg/I18nTextTable'
import type { ItemTable } from '@/types/endfielddata/TableCfg/ItemTable'
import type { RarityColorTable } from '@/types/endfielddata/TableCfg/RarityColorTable'
import type { SkillPatchTable } from '@/types/endfielddata/TableCfg/SkillPatchTable'
import type { TextTable } from '@/types/endfielddata/TableCfg/TextTable'
import type { WeaponBasicTable } from '@/types/endfielddata/TableCfg/WeaponBasicTable'
import type { WikiEntryDataTable } from '@/types/endfielddata/TableCfg/WikiEntryDataTable'
import type { WikiEntryTable } from '@/types/endfielddata/TableCfg/WikiEntryTable'
import type { WikiGroupTable } from '@/types/endfielddata/TableCfg/WikiGroupTable'
import type { WorldEnergyPointGroupTable } from '@/types/endfielddata/TableCfg/WorldEnergyPointGroupTable'
import type { WorldEnergyPointTable } from '@/types/endfielddata/TableCfg/WorldEnergyPointTable'
import { useLanguage } from '@/composables/useLanguage'
import { ref } from 'vue'

/** 获取指定语言的国际化文本表路径 */
function getI18nTextTablePath(language: string) {
  return `endfielddata/TableCfg/I18nTextTable_${language}.json`
}

/** 获取资源的完整 URL */
function getResourceUrl(resourcePath: string): string {
  return `${import.meta.env.VITE_API_BASE_URL}/api/data/${resourcePath}`
}

/**
 * 解析带有大整数的 JSON 的辅助函数
 * 将看起来像 ID 的数值（长整数）替换为字符串，避免 JSON.parse 时丢失精度
 * 目前的实现方法是简单地将所有 "id": <number> 替换为 "id": "<number>"
 */
function parseJSONWithBigInt(text: string) {
  const replaced = text.replace(/"id":\s*(-?\d+)/g, '"id": "$1"')
  return JSON.parse(replaced)
}

/**
 * 获取指定语言的文本内容
 * 如果找不到翻译或翻译为空，返回原始文本
 * 如果不指定语言，使用当前选择的语言
 */
export function getTranslation({ id, text }: TranslationKey, language?: string): string {
  const { currentLanguage } = useLanguage()
  const lang = language ?? currentLanguage.value

  const translation = i18nTextTables.value.get(lang)?.[String(id)]
  if (translation !== undefined) {
    return translation.trim()
  } else {
    return text
  }
}

const gemTablePath = 'endfielddata/TableCfg/GemTable.json'
const gemTagIdTablePath = 'endfielddata/TableCfg/GemTagIdTable.json'
const itemTablePath = 'endfielddata/TableCfg/ItemTable.json'
const rarityColorTablePath = 'endfielddata/TableCfg/RarityColorTable.json'
const skillPatchTablePath = 'endfielddata/TableCfg/SkillPatchTable.json'
const textTablePath = 'endfielddata/TableCfg/TextTable.json'
const weaponBasicTablePath = 'endfielddata/TableCfg/WeaponBasicTable.json'
const wikiEntryDataTablePath = 'endfielddata/TableCfg/WikiEntryDataTable.json'
const wikiEntryTablePath = 'endfielddata/TableCfg/WikiEntryTable.json'
const wikiGroupTablePath = 'endfielddata/TableCfg/WikiGroupTable.json'
const i18nLanguages = ['CN', 'EN', 'JP', 'KR', 'MX', 'RU', 'TC']
const usedLanguages = ['CN', 'EN', 'JP', 'KR', 'MX', 'RU', 'TC']

export const gemTable = ref<GemTable>({})
export const gemTagIdTable = ref<GemTagIdTable>({})
export const itemTable = ref<ItemTable>({})
export const rarityColorTable = ref<RarityColorTable>({})
export const skillPatchTable = ref<SkillPatchTable>({})
export const textTable = ref<TextTable>({})
export const weaponBasicTable = ref<WeaponBasicTable>({})
export const wikiEntryDataTable = ref<WikiEntryDataTable>({})
export const wikiEntryTable = ref<WikiEntryTable>({})
export const wikiGroupTable = ref<WikiGroupTable>({})
export const worldEnergyPointGroupTable = ref<WorldEnergyPointGroupTable>({})
export const worldEnergyPointTable = ref<WorldEnergyPointTable>({})
export const i18nTextTables = ref<Map<string, I18nTextTable>>(new Map())
export const isLoaded = ref(false)

// 并行加载所有需要的解包数据
export async function initGameData() {
  if (isLoaded.value) return

  console.log('Initializing game data...')

  await Promise.all([
    fetch(getResourceUrl(gemTablePath))
      .then((res) => res.text())
      .then((text) => {
        gemTable.value = parseJSONWithBigInt(text)
      }),
    // fetch(getResourceUrl(gemTagIdTablePath))
    //   .then((res) => res.text())
    //   .then((text) => {
    //     gemTagIdTable.value = parseJSONWithBigInt(text)
    //   }),
    fetch(getResourceUrl(itemTablePath))
      .then((res) => res.text())
      .then((text) => {
        itemTable.value = parseJSONWithBigInt(text)
      }),
    fetch(getResourceUrl(rarityColorTablePath))
      .then((res) => res.text())
      .then((text) => {
        rarityColorTable.value = parseJSONWithBigInt(text)
      }),
    // fetch(getResourceUrl(skillPatchTablePath))
    //   .then((res) => res.text())
    //   .then((text) => {
    //     skillPatchTable.value = parseJSONWithBigInt(text)
    //   }),
    // fetch(getResourceUrl(textTablePath))
    //   .then((res) => res.text())
    //   .then((text) => {
    //     textTable.value = parseJSONWithBigInt(text)
    //   }),
    fetch(getResourceUrl(weaponBasicTablePath))
      .then((res) => res.text())
      .then((text) => {
        weaponBasicTable.value = parseJSONWithBigInt(text)
      }),
    fetch(getResourceUrl(wikiEntryDataTablePath))
      .then((res) => res.text())
      .then((text) => {
        wikiEntryDataTable.value = parseJSONWithBigInt(text)
      }),
    fetch(getResourceUrl(wikiEntryTablePath))
      .then((res) => res.text())
      .then((text) => {
        wikiEntryTable.value = parseJSONWithBigInt(text)
      }),
    fetch(getResourceUrl(wikiGroupTablePath))
      .then((res) => res.text())
      .then((text) => {
        wikiGroupTable.value = parseJSONWithBigInt(text)
      }),
    ...usedLanguages.map((language) =>
      fetch(getResourceUrl(getI18nTextTablePath(language)))
        .then((res) => res.text())
        .then((text) => {
          const table = JSON.parse(text)
          i18nTextTables.value.set(language, table)
        }),
    ),
  ])

  isLoaded.value = true

  console.log('Game data initialized.')
}
