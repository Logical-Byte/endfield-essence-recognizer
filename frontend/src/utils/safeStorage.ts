export function safeLoadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch (error) {
    try {
      localStorage.removeItem(key)
    } catch {
      // 清理失败不影响返回默认值
    }
    console.warn(`读取 localStorage 键 "${key}" 失败`, error)
    return fallback
  }
}

export function safeSetJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (error) {
    console.warn(`写入 localStorage 键 "${key}" 失败`, error)
  }
}

export function safeRemoveJson(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch (error) {
    console.warn(`删除 localStorage 键 "${key}" 失败`, error)
  }
}
