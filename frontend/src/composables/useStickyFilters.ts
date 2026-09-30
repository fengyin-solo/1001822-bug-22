import { reactive, watch } from 'vue'

/**
 * 把筛选条件记到 localStorage：切走页面、关掉浏览器下次进来，
 * 上次选好的条件还在。key 按页面区分，互不干扰。
 */
export function useStickyFilters(key: string) {
  const storageKey = `filters:${key}`

  function read(): Record<string, string> {
    try {
      const raw = window.localStorage.getItem(storageKey)
      return raw ? (JSON.parse(raw) as Record<string, string>) : {}
    } catch {
      return {}
    }
  }

  const filters = reactive<Record<string, string>>(read())

  watch(
    filters,
    (value) => {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(value))
      } catch {
        // 隐私模式等场景写不进去时静默降级，不影响查询本身
      }
    },
    { deep: true },
  )

  function clearPersisted() {
    for (const keyName of Object.keys(filters)) {
      delete filters[keyName]
    }
    try {
      window.localStorage.removeItem(storageKey)
    } catch {
      // 同静默降级
    }
  }

  return { filters, clearPersisted }
}
