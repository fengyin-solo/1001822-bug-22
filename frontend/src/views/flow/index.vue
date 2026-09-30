<template>
  <section class="page" data-module="flow">
    <header class="page-head">
      <div>
        <h2>流量监测管理</h2>
        <p class="page-desc">维护流量记录，围绕监测编号、监测断面、监测时段、平均流量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn primary" type="button" to="/flow/new">登记流量记录</RouterLink>
        <button class="btn" type="button" @click="exportRows">导出流量监测清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="() => reload()">
      <label class="filter-item">
        <span>监测编号</span>
        <input v-model="filters.keyword" placeholder="按监测编号检索" />
      </label>
      <label class="filter-item">
        <span>监测断面</span>
        <input v-model="filters.section" placeholder="按监测断面检索" />
      </label>
      <label class="filter-item">
        <span>监测时段</span>
        <input v-model="filters.period" placeholder="按监测时段检索" />
      </label>
      <label class="filter-item">
        <span>监测状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <RouterLink v-if="column === '监测编号'" class="link" :to="`/flow/${row.id}`">
              {{ row[column] ?? '—' }}
            </RouterLink>
            <template v-else>{{ column === '监测状态' ? (row.status ?? '—') : (row[column] ?? '—') }}</template>
          </td>
          <td class="row-actions">
            <RouterLink class="link" :to="`/flow/${row.id}`">查看/修改</RouterLink>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="pendingAction === `${row.id}:${action}`"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无流量监测数据，可先登记流量记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条流量监测记录</span>
      <span v-if="successMessage" class="success-text">{{ successMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useStickyFilters } from '@/composables/useStickyFilters'

type Row = Record<string, string | number | boolean | null>
type Stats = { total: number; monitoring: number; abnormal: number; today_total: number }

const ENDPOINT = '/api/flow'
const columns = ['监测编号', '监测断面', '监测时段', '平均流量', '峰值流量', '累计流量', '采集人员', '监测状态']
const actions = ['启动采集', '标记异常', '停止监测']
const statuses = ['待采集', '采集正常', '流量异常', '已停测']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const pendingAction = ref('')
const { filters, clearPersisted } = useStickyFilters('flow')

const stats = ref([
  { label: '在测断面', value: 0 },
  { label: '流量异常断面', value: 0 },
  { label: '今日累计流量', value: 0 },
])

// 卡片指标取后端 /stats，与运营概览同一口径，三处条数始终一致
async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) {
      return
    }
    const data = (await response.json()) as Stats
    stats.value = [
      { label: '在测断面', value: data.monitoring },
      { label: '流量异常断面', value: data.abnormal },
      { label: '今日累计流量', value: data.today_total },
    ]
  } catch {
    // 卡片读不到不阻塞列表，错误在列表请求里统一提示
  }
}

function resetFilters() {
  clearPersisted()
  errorMessage.value = ''
  void reload()
}

function exportRows() {
  const query = new URLSearchParams(
    Object.fromEntries(Object.entries(filters).filter(([, value]) => value)),
  ).toString()
  window.open(`${ENDPOINT}/export?${query}`, '_blank')
}

async function readActionError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { message?: string; detail?: string }
    return payload.message ?? payload.detail ?? fallback
  } catch {
    return fallback
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  successMessage.value = ''
  const actionKey = `${row.id}:${action}`
  pendingAction.value = actionKey
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string } | null
    if (!response.ok || payload?.ok === false) {
      throw new Error(await readActionError(response, '流量监测动作未生效，请稍后重试'))
    }
    successMessage.value = payload?.message ?? `流量记录已${action}`
    await Promise.all([reload(false), loadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '流量监测操作失败'
  } finally {
    pendingAction.value = ''
  }
}

async function reload(showSuccess = true) {
  errorMessage.value = ''
  if (showSuccess) {
    successMessage.value = ''
  }
  const params = new URLSearchParams()
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.section) params.set('section', filters.section)
  if (filters.status) params.set('status', filters.status)
  if (filters.period) params.set('period', filters.period)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error(await readActionError(response, '流量记录列表读取失败'))
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '流量监测列表读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>
