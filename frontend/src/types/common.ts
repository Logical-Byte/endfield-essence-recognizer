export interface TranslationKey {
  id: string | number // 在解包数据中是 64 位有符号整数，解析时转换为 string 避免精度丢失
  text: string
}
