import { ref, watch } from 'vue'

export type Language =
  | 'CN'
  | 'TC'
  | 'DE'
  | 'EN'
  | 'MX'
  | 'FR'
  | 'BR'
  | 'ID'
  | 'IT'
  | 'JP'
  | 'KR'
  | 'RU'
  | 'TH'
  | 'VN'

const STORAGE_KEY = 'app-language'

// 从 localStorage 读取保存的语言，默认为中文
const currentLanguage = ref<Language>((localStorage.getItem(STORAGE_KEY) as Language) || 'CN')

const usedLanguages: Language[] = [
  'CN',
  'TC',
  'DE',
  'EN',
  'MX',
  'FR',
  'BR',
  'ID',
  'IT',
  'JP',
  'KR',
  'RU',
  'TH',
  'VN',
]

const languageToText = new Map<Language, string>([
  ['CN', '简体中文'],
  ['TC', '繁體中文'],
  ['DE', 'Deutsch'],
  ['EN', 'English'],
  ['MX', 'Español'],
  ['FR', 'Français'],
  ['BR', 'Português (Brasil)'],
  ['IT', 'Italiano'],
  ['JP', '日本語'],
  ['KR', '한국어'],
  ['ID', 'Bahasa Indonesia'],
  ['RU', 'Русский'],
  ['TH', 'ภาษาไทย'],
  ['VN', 'Tiếng Việt'],
])

// 监听语言变化并保存到 localStorage
watch(currentLanguage, (newLang) => {
  localStorage.setItem(STORAGE_KEY, newLang)
})

export function useLanguage() {
  const setLanguage = (lang: Language) => {
    currentLanguage.value = lang
  }

  return {
    usedLanguages,
    languageToText,
    currentLanguage,
    setLanguage,
  }
}
