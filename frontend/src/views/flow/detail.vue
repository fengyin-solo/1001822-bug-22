<template>
  <section class="page" data-module="flow-detail">
    <header class="page-head">
      <div>
        <h2>流量记录详情</h2>
        <p class="page-desc">查看并修改单条流量记录；保存失败时原值保留并说明原因，保存成功后重开页面仍是最新值。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <div v-if="loading" class="empty-state">正在读取流量记录…</div>

    <article v-else-if="entry" class="detail-card">
      <div class="detail-status">
        <span>记录 ID：{{ entry.id }}</span>
        <span>监测状态：<strong>{{ entry['监测状态'] }}</strong></span>
      </div>

      <p v-if="message" :class="saveOk ? 'ok-text' : 'error-text'">{{ message }}</p>

      <form class="detail-form" @submit.prevent="save">
        <label v-for="field in editableFields" :key="field" class="filter-item">
          <span>{{ field }}<em v-if="requiredFields.includes(field)">*</em></span>
          <input v-model="form[field]" :disabled="saving" :placeholder="`请输入${field}`" />
        </label>
        <div class="page-actions">
          <button class="btn primary" type="submit" :disabled="saving">
            {{ saving ? '保存中…' : '保存' }}
          </button>
          <button class="btn ghost" type="button" :disabled="saving" @click="resetForm">还原为已保存值</button>
        </div>
      </form>
    </article>

    <div v-else class="empty-state">
      <p class="error-text">{{ loadError || '未找到该流量记录' }}</p>
      <button class="btn" type="button" @click="goBack">返回列表</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Entry = Record<string, string | number | null>

const route = useRoute()
const router = useRouter()
const ENDPOINT = `/api/flow/${String(route.params.id)}`

const editableFields = ['监测编号', '监测断面', '监测时段', '平均流量', '峰值流量', '累计流量', '采集人员']
const requiredFields = ['监测编号', '监测断面', '监测时段']

const loading = ref(true)
const entry = ref<Entry | null>(null)
const form = ref<Record<string, string>>({})
const savedSnapshot = ref<Record<string, string>>({})
const saving = ref(false)
const message = ref('')
const saveOk = ref(false)
const loadError = ref('')

function fillForm(source: Entry) {
  const next: Record<string, string> = {}
  for (const field of editableFields) {
    const value = source[field]
    next[field] = value === null || value === undefined ? '' : String(value)
  }
  form.value = next
  // 已保存快照：校验失败时表单不动，用户还能用“还原为已保存值”一键回到库中现状
  savedSnapshot.value = { ...next }
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await request(ENDPOINT)
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.detail || `流量记录读取失败（${response.status}）`)
    }
    const data: Entry = await response.json()
    entry.value = data
    fillForm(data)
  } catch (error) {
    entry.value = null
    loadError.value = error instanceof Error ? error.message : '流量记录读取失败'
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.value = { ...savedSnapshot.value }
  message.value = ''
}

async function save() {
  if (saving.value) return // 保存途中重复点击只算一次
  saving.value = true
  message.value = ''
  saveOk.value = false
  try {
    const response = await request(ENDPOINT, {
      method: 'PUT',
      body: JSON.stringify({ values: { ...form.value } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      // 关键：不落库时不覆盖表单，原值（用户输入）保留，只把原因讲清楚
      saveOk.value = false
      message.value = payload?.message || '保存未成功，原值已保留，请调整后重试'
      return
    }
    saveOk.value = true
    message.value = payload.message || '保存成功'
    if (payload.entry) {
      entry.value = payload.entry as Entry
      fillForm(payload.entry as Entry)
    }
  } catch (error) {
    saveOk.value = false
    message.value = error instanceof Error ? error.message : '保存请求未送达，原值已保留'
  } finally {
    saving.value = false
  }
}

function goBack() {
  // 列表组件会在挂载时重新拉取，退回后看到的就是刚保存的最新状态
  void router.push('/flow')
}

onMounted(load)
</script>

<style scoped>
.detail-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 18px;
  max-width: 720px;
}
.detail-status {
  display: flex;
  gap: 24px;
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 12px;
}
.detail-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}
.detail-form .page-actions {
  grid-column: 1 / -1;
  justify-content: flex-end;
}
.detail-form em {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.ok-text { color: #067647; }
</style>
