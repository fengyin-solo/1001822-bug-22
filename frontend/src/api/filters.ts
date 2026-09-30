/**
 * 列表筛选条件的本地持久化：离开页面或下次再进来时，
 * 仍能还原上次选好的条件，而不是每次回到空白。
 */
export function loadFilters(storageKey: string): Record<string, string> {
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return {}
    const result: Record<string, string> = {}
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof value === 'string') result[key] = value
    }
    return result
  } catch {
    return {}
  }
}

export function saveFilters(storageKey: string, filters: Record<string, string>): void {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(filters))
  } catch {
    // 隐私模式或存储写满时静默降级：筛选只是辅助，不应阻断业务操作
  }
}

export function clearFilters(storageKey: string): void {
  try {
    window.localStorage.removeItem(storageKey)
  } catch {
    // 同上，忽略清理失败
  }
}
