<template>
  <section class="page" data-module="flow">
    <header class="page-head">
      <div>
        <h2>流量监测管理</h2>
        <p class="page-desc">维护流量记录，围绕监测编号、监测断面、监测时段、平均流量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记流量记录</button>
        <button class="btn" type="button" @click="exportRows">导出流量监测清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <RouterLink class="link" :to="`/flow/${row.id}`">详情</RouterLink>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="pendingKey === `${row.id}:${action}`"
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
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="creating" class="modal-mask" @click.self="closeCreate">
      <div class="modal-card">
        <h3>登记流量记录</h3>
        <p v-if="createMessage" :class="createOk ? 'ok-text' : 'error-text'">{{ createMessage }}</p>
        <label v-for="field in createFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <div class="page-actions">
          <button class="btn primary" type="button" :disabled="saving" @click="submitCreate">
            {{ saving ? '提交中…' : '保存' }}
          </button>
          <button class="btn ghost" type="button" :disabled="saving" @click="closeCreate">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { clearFilters, loadFilters, saveFilters } from '@/api/filters'

type Row = Record<string, string | number | null>
type FlowStats = {
  monitoring: number
  abnormal: number
  today_total: number
  total: number
  pending: number
}

const ENDPOINT = '/api/flow'
const FILTER_STORAGE_KEY = 'flow:filters'
const columns = ['监测编号', '监测断面', '监测时段', '平均流量', '峰值流量', '累计流量', '采集人员', '监测状态']
const actions = ['启动采集', '标记异常', '停止监测']
const filterFields = columns.slice(0, 3)
const createFields = ['监测编号', '监测断面', '监测时段', '平均流量', '峰值流量', '累计流量', '采集人员']
// 筛选输入框（中文键）到后端查询参数的映射，保证填的条件真的能过滤
const FILTER_PARAMS: Record<string, string> = {
  监测编号: 'keyword',
  监测断面: 'section',
  监测时段: 'period',
}

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
// 初始值直接从 localStorage 还原，下次进来还是上次选好的条件
const filters = ref<Record<string, string>>(loadFilters(FILTER_STORAGE_KEY))
const stats = ref([
  { label: '在测断面', value: 0 },
  { label: '流量异常断面', value: 0 },
  { label: '今日累计流量', value: 0 },
])
const pendingKey = ref('')

const creating = ref(false)
const saving = ref(false)
const createMessage = ref('')
const createOk = ref(false)
const createForm = ref<Record<string, string>>({})

function buildQuery(extra?: Record<string, string>): string {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = (extra?.[field] ?? filters.value[field] ?? '').trim()
    if (value) params.set(FILTER_PARAMS[field], value)
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

function resetFilters() {
  filters.value = {}
  clearFilters(FILTER_STORAGE_KEY)
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export${buildQuery()}`, '_blank')
}

function openCreate() {
  creating.value = true
  saving.value = false
  createMessage.value = ''
  createOk.value = false
  createForm.value = {}
}

function closeCreate() {
  creating.value = false
}

async function submitCreate() {
  if (saving.value) return // 重复点击只提交一次
  saving.value = true
  createMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      createOk.value = false
      createMessage.value = payload?.message || '登记失败，请检查填写内容后重试'
      return
    }
    createOk.value = true
    createMessage.value = payload.message || '流量记录已登记'
    createForm.value = {}
    await reload()
  } catch (error) {
    createOk.value = false
    createMessage.value = error instanceof Error ? error.message : '流量记录登记失败'
  } finally {
    saving.value = false
  }
}

async function runAction(action: string, row: Row) {
  const key = `${row.id}:${action}`
  if (pendingKey.value === key) return // 同一动作在途，不重复发
  errorMessage.value = ''
  pendingKey.value = key
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '流量监测动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '流量监测操作失败'
  } finally {
    pendingKey.value = ''
  }
}

async function reload() {
  errorMessage.value = ''
  saveFilters(FILTER_STORAGE_KEY, filters.value)
  try {
    const response = await request(`${ENDPOINT}${buildQuery()}`)
    if (!response.ok) {
      throw new Error('流量记录列表读取失败')
    }
    const payload: { items?: Row[]; total?: number; stats?: FlowStats } = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (payload.stats) {
      // 与运营概览同一份口径：数字由后端统一下发，页面不再各算各的
      stats.value = [
        { label: '在测断面', value: payload.stats.monitoring },
        { label: '流量异常断面', value: payload.stats.abnormal },
        { label: '今日累计流量', value: payload.stats.today_total },
      ]
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '流量监测列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-card {
  width: 420px;
  background: #fff;
  border-radius: 8px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.modal-card .filter-item { display: flex; flex-direction: column; gap: 4px; }
.modal-card .page-actions { justify-content: flex-end; margin-top: 4px; }
.ok-text { color: #067647; }
.link:disabled { color: #94a3b8; cursor: default; }
</style>
