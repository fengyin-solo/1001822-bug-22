<template>
  <section class="page" data-module="flow-edit">
    <header class="page-head">
      <div>
        <h2>{{ isCreate ? '登记流量记录' : `流量记录明细 · ${entryId}` }}</h2>
        <p class="page-desc">
          {{ isCreate ? '录入监测编号、断面、时段与流量数据，保存成功后回到列表即可看到最新值。' : '修改后点保存即落库；保存不成功时输入内容保留，并在下方说明原因。' }}
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/flow">返回列表</RouterLink>
      </div>
    </header>

    <div v-if="loading" class="form-card">正在读取记录…</div>

    <form v-else class="form-card" @submit.prevent="save">
      <div v-if="!isCreate" class="form-row">
        <span class="form-label">当前监测状态</span>
        <strong>{{ form.status || '—' }}</strong>
        <span class="form-hint">状态由列表页的「启动采集 / 标记异常 / 停止监测」流转，不在此直接编辑</span>
      </div>

      <label v-for="field in fields" :key="field.key" class="form-row">
        <span class="form-label">
          {{ field.label }}<em v-if="field.required" class="required">*</em>
        </span>
        <input
          v-model="form[field.key]"
          :inputmode="field.numeric ? 'decimal' : undefined"
          :placeholder="`请输入${field.label}`"
        />
      </label>

      <div class="form-actions">
        <button class="btn primary" type="submit" :disabled="saving">
          {{ saving ? '保存中…' : '保存' }}
        </button>
        <RouterLink class="btn ghost" to="/flow">取消并返回</RouterLink>
      </div>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <p v-if="successMessage" class="success-text">{{ successMessage }}</p>
    </form>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type FormState = {
  status: string
  监测编号: string
  监测断面: string
  监测时段: string
  平均流量: string
  峰值流量: string
  累计流量: string
  采集人员: string
  [key: string]: string
}

const route = useRoute()
const router = useRouter()

const entryId = route.name === 'flow-create' ? '' : String(route.params.id ?? '')
const isCreate = !entryId

type FieldDef = {
  key: '监测编号' | '监测断面' | '监测时段' | '平均流量' | '峰值流量' | '累计流量' | '采集人员'
  label: string
  required?: boolean
  numeric?: boolean
}

const fields: FieldDef[] = [
  { key: '监测编号', label: '监测编号', required: true },
  { key: '监测断面', label: '监测断面', required: true },
  { key: '监测时段', label: '监测时段', required: true },
  { key: '平均流量', label: '平均流量', numeric: true },
  { key: '峰值流量', label: '峰值流量', numeric: true },
  { key: '累计流量', label: '累计流量', numeric: true },
  { key: '采集人员', label: '采集人员' },
]

function emptyForm(): FormState {
  return reactive({
    status: '',
    监测编号: '',
    监测断面: '',
    监测时段: '',
    平均流量: '',
    峰值流量: '',
    累计流量: '',
    采集人员: '',
  })
}

const form = emptyForm()
const loading = ref(!isCreate)
const saving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

async function loadEntry() {
  if (isCreate) {
    return
  }
  try {
    const response = await request(`/api/flow/${entryId}`)
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null
      throw new Error(payload?.detail ?? `流量记录 ${entryId} 读取失败`)
    }
    const data = await response.json()
    for (const field of fields) {
      const raw = data[field.key] == null ? '' : String(data[field.key])
      if (field.numeric && raw.trim() !== '' && Number.isNaN(Number(raw))) {
        // 历史占位文本（非数字）不作为真实流量回显，按空值处理，避免占位文本挡住保存
        form[field.key] = ''
      } else {
        form[field.key] = raw
      }
    }
    form.status = String(data.status ?? '')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '流量记录读取失败'
  } finally {
    loading.value = false
  }
}

async function save() {
  errorMessage.value = ''
  successMessage.value = ''
  saving.value = true
  try {
    const values: Record<string, string> = {}
    for (const field of fields) {
      values[field.key] = form[field.key].trim()
    }
    // 流量字段填了就必须是数字；不填可以（历史占位文本已按空值处理）
    const badNumeric = fields
      .filter((field) => field.numeric && values[field.key] !== '' && Number.isNaN(Number(values[field.key])))
      .map((field) => field.label)
    if (badNumeric.length) {
      // 校验不过：不发请求，输入原样保留并说明原因
      throw new Error(`流量字段必须是数字：${badNumeric.join('、')}`)
    }
    const url = isCreate ? '/api/flow' : `/api/flow/${entryId}`
    const response = await request(url, {
      method: isCreate ? 'POST' : 'PUT',
      body: JSON.stringify({ values }),
    })
    const payload = (await response.json().catch(() => null)) as
      | { ok?: boolean; message?: string; entry?: Record<string, unknown> }
      | null
    if (!response.ok || payload?.ok === false) {
      // 保存不成功：表单值原样保留，只说明原因，不跳转、不清空
      throw new Error(payload?.message ?? '保存未成功，请检查输入后重试')
    }
    successMessage.value = payload?.message ?? '保存成功'
    if (isCreate && payload?.entry?.id != null) {
      // 登记成功后跳到对应明细页，再退回列表看到的就是最新值
      await router.replace(`/flow/${payload.entry.id}`)
      return
    }
    if (payload?.entry?.status != null) {
      form.status = String(payload.entry.status)
    }
    // 稍作停留让成功提示可见，再回列表
    window.setTimeout(() => {
      void router.push('/flow')
    }, 400)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存未成功，请稍后重试'
  } finally {
    saving.value = false
  }
}

onMounted(loadEntry)
</script>
