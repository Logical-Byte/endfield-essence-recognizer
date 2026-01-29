import { ref, watch } from 'vue'

export type Language = 'CN' | 'EN' | 'JP' | 'KR' | 'MX' | 'RU' | 'TC'

const STORAGE_KEY = 'app-language'

// 从 localStorage 读取保存的语言，默认为中文
const currentLanguage = ref<Language>((localStorage.getItem(STORAGE_KEY) as Language) || 'CN')

const usedLanguages: Language[] = ['CN', 'EN', 'JP', 'KR', 'MX', 'RU', 'TC']

const languageToText = new Map<Language, string>([
  ['CN', '简体中文'],
  ['EN', 'English'],
  ['JP', '日本語'],
  ['KR', '한국어'],
  ['MX', 'Español'],
  ['RU', 'Русский'],
  ['TC', '繁體中文'],
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
