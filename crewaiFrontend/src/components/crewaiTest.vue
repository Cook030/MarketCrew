<template>
  <section class="crew-form-container">
    <h1>营销任务</h1>
    <p class="intro">填写客户网址和本次目标，准备项目材料。</p>

    <el-form ref="crewForm" :model="form" :rules="rules" label-position="top">
      <el-form-item label="网址" prop="customer_domain">
        <el-input v-model="form.customer_domain" placeholder="https://example.com" :disabled="starting" />
      </el-form-item>

      <el-form-item label="本次任务目标" prop="task_goal">
        <el-input
          v-model="form.task_goal"
          type="textarea"
          :rows="3"
          maxlength="4000"
          show-word-limit
          placeholder="例如：面向年轻通勤人群，为新品制定推广策略并生成社交媒体文案。"
          :disabled="starting"
        />
        <p class="field-help">说明这次希望完成什么，以及目标受众或其他要求。</p>
      </el-form-item>

      <el-form-item label="上传材料">
        <div class="materials">
          <el-alert
            title="项目材料知识库"
            description="选择材料后点击“上传并建立知识库”，处理完成后，分析、策略和文案任务将共享这份材料。材料可选。"
            type="info"
            :closable="false"
            show-icon
          />
          <el-upload
            ref="materialUpload"
            v-model:file-list="materialFiles"
            drag
            multiple
            :auto-upload="false"
            :show-file-list="false"
            :accept="MATERIAL_ACCEPT"
            :limit="MAX_MATERIAL_FILES"
            :disabled="starting || materialsBusy"
            :on-change="handleMaterialChange"
            :on-exceed="handleMaterialExceed"
          >
            <p class="upload-title">拖入材料，或点击选择文件</p>
            <template #tip>
              <p class="field-help">支持 DOCX、PDF、MD、HTML；最多 5 个文件，每个不超过 10 MB。暂不支持旧版 DOC 和扫描件文字识别。</p>
            </template>
          </el-upload>
          <ul v-if="materialFiles.length" class="material-list" aria-label="已选择的材料">
            <li v-for="(file, index) in materialFiles" :key="file.uid">
              <div class="material-info">
                <span class="file-name">{{ file.name }}</span>
                <el-tag :type="knowledgeBase?.status === 'READY' ? 'success' : knowledgeBase?.status === 'ERROR' ? 'danger' : 'info'" size="small">
                  {{ materialStatus(index) }}
                </el-tag>
              </div>
              <el-button
                text
                type="danger"
                :disabled="starting || materialsBusy"
                :aria-label="`移除 ${file.name}`"
                @click="removeMaterial(file)"
              >移除</el-button>
            </li>
          </ul>
          <el-button
            v-if="materialFiles.length"
            class="build-knowledge-button"
            :loading="materialsBusy"
            :disabled="starting || knowledgeBase?.status === 'READY'"
            @click="uploadMaterials"
          >{{ knowledgeBase?.status === 'ERROR' ? '重新上传并建立知识库' : '上传并建立知识库' }}</el-button>
          <p v-if="materialFiles.length" class="material-notice" :data-status="knowledgeBase?.status" role="status">
            {{ knowledgeBase?.message || '材料仅已选择，尚未上传。请先建立知识库。' }}
          </p>
          <p v-if="knowledgeBase?.status === 'READY'" class="field-help">
            已接入 {{ materialFiles.length }} 个文件，共 {{ knowledgeBase.chunk_count }} 个正文片段。
          </p>
          <el-button v-if="pollingFailed" text @click="refreshKnowledgeBase">重新查询材料状态</el-button>
        </div>
      </el-form-item>

      <div class="actions">
        <el-button
          type="primary"
          :loading="starting"
          :disabled="(materialFiles.length > 0 && knowledgeBase?.status !== 'READY') || materialsBusy || refreshing"
          @click="startTask"
        >启动任务</el-button>
        <el-button :loading="refreshing" :disabled="!jobId || starting" @click="refreshTask">刷新结果</el-button>
      </div>
    </el-form>

    <div v-if="jobId" class="job-info" role="status">
      <span>任务 ID：{{ jobId }}</span>
      <span>状态：{{ jobStatus }}</span>
    </div>
    <div v-if="jobSources.length" class="sources">
      <p>任务检索过的材料片段（具体结论的引用见生成结果）</p>
      <ul>
        <li v-for="source in jobSources" :key="source.chunk_id">
          {{ source.filename }} · {{ source.location }} · {{ source.chunk_id }}
        </li>
      </ul>
    </div>
    <div v-if="errorMessage" class="error-message" role="alert">
      <el-alert :title="errorMessage" type="error" :closable="false" show-icon />
    </div>

    <div class="result">
      <label for="crew-result">任务结果</label>
      <el-input
        id="crew-result"
        v-model="resultContent"
        type="textarea"
        :rows="10"
        readonly
        placeholder="启动任务后，点击“刷新结果”查看进度和结果。"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import {
  MATERIAL_ACCEPT,
  MAX_MATERIAL_FILES,
  buildCrewPayload,
  getMaterialError,
  getWebsiteError,
} from '../form-utils.js'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8012/api'
const API_URL = `${API_BASE}/crew`
const form = ref({ customer_domain: '', task_goal: '' })
const crewForm = ref(null)
const materialUpload = ref(null)
const materialFiles = ref([])
const knowledgeBase = ref(null)
const uploading = ref(false)
const pollingFailed = ref(false)
const materialsBusy = computed(() => uploading.value || ['PENDING', 'PROCESSING'].includes(knowledgeBase.value?.status))
let pollingTimer
const materialRequests = new AbortController()
const starting = ref(false)
const refreshing = ref(false)
const jobId = ref('')
const jobStatus = ref('')
const resultContent = ref('')
const errorMessage = ref('')
const jobSources = ref([])

const rules = {
  customer_domain: [{
    required: true,
    trigger: 'blur',
    validator: (_rule, value, callback) => {
      const message = getWebsiteError(value)
      callback(message ? new Error(message) : undefined)
    },
  }],
  task_goal: [{ required: true, whitespace: true, message: '请输入本次任务目标', trigger: 'blur' }],
}

function handleMaterialChange(file) {
  const message = getMaterialError(file.raw)
  if (message) {
    materialUpload.value.handleRemove(file)
    ElMessage.error(message)
    return
  }
  resetKnowledgeBase()
}

function handleMaterialExceed() {
  ElMessage.warning(`最多选择 ${MAX_MATERIAL_FILES} 个文件，请移除部分材料后重试`)
}

function removeMaterial(file) {
  materialUpload.value.handleRemove(file)
  resetKnowledgeBase()
}

function resetKnowledgeBase() {
  clearTimeout(pollingTimer)
  knowledgeBase.value = null
  pollingFailed.value = false
  errorMessage.value = ''
}

function materialStatus(index) {
  const status = knowledgeBase.value?.files[index]?.status
  return { PENDING: '已上传 · 待处理', PROCESSING: '正在解析', PARSED: '已解析 · 建立索引中', READY: '已接入', ERROR: '处理失败' }[status] || '已选择 · 待上传'
}

async function uploadMaterials() {
  if (!materialFiles.value.length || materialsBusy.value || starting.value) return
  resetKnowledgeBase()
  uploading.value = true
  try {
    const body = new FormData()
    for (const file of materialFiles.value) body.append('files', file.raw)
    const response = await axios.post(`${API_BASE}/knowledge-bases`, body, { signal: materialRequests.signal })
    knowledgeBase.value = response.data
    if (['PENDING', 'PROCESSING'].includes(response.data.status)) {
      pollingTimer = setTimeout(refreshKnowledgeBase, 1500)
    }
  } catch (error) {
    if (!axios.isCancel(error)) showRequestError(error, '材料上传失败，请确认服务可用后重试')
  } finally {
    uploading.value = false
  }
}

async function refreshKnowledgeBase() {
  if (!knowledgeBase.value) return
  clearTimeout(pollingTimer)
  pollingFailed.value = false
  try {
    const response = await axios.get(`${API_BASE}/knowledge-bases/${knowledgeBase.value.knowledge_base_id}`, {
      signal: materialRequests.signal,
    })
    knowledgeBase.value = response.data
    if (['PENDING', 'PROCESSING'].includes(response.data.status)) {
      pollingTimer = setTimeout(refreshKnowledgeBase, 1500)
    }
  } catch (error) {
    if (!axios.isCancel(error)) {
      pollingFailed.value = true
      showRequestError(error, '材料状态查询失败，请点击“重新查询材料状态”')
    }
  }
}

onUnmounted(() => {
  clearTimeout(pollingTimer)
  materialRequests.abort()
})

function showRequestError(error, fallback) {
  const detail = error.response?.data?.message
  errorMessage.value = typeof detail === 'string' ? detail : fallback
}

async function startTask() {
  if (starting.value || refreshing.value) return
  errorMessage.value = ''
  starting.value = true
  try {
    const isValid = await crewForm.value.validate().catch(() => false)
    if (!isValid) return
    const payload = buildCrewPayload(form.value, materialFiles.value, knowledgeBase.value)
    const response = await axios.post(API_URL, payload)
    if (!response.data.job_id) throw new Error('Missing job_id')
    jobId.value = response.data.job_id
    jobStatus.value = '已提交'
    resultContent.value = ''
    jobSources.value = []
    ElMessage.success(materialFiles.value.length ? '任务已提交，将使用项目材料知识库' : '任务已提交')
  } catch (error) {
    showRequestError(error, '任务未能提交，请确认服务可用后重试')
  } finally {
    starting.value = false
  }
}

async function refreshTask() {
  if (!jobId.value || refreshing.value || starting.value) return
  errorMessage.value = ''
  refreshing.value = true
  try {
    const response = await axios.get(`${API_URL}/${encodeURIComponent(jobId.value)}`)
    jobStatus.value = response.data.status
    resultContent.value = JSON.stringify(response.data, null, 2)
    jobSources.value = response.data.sources || []
  } catch (error) {
    showRequestError(error, '未能获取任务结果，请稍后重试')
  } finally {
    refreshing.value = false
  }
}
</script>

<style scoped>
.crew-form-container {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  padding: 28px;
  color: #303133;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
}

h1 {
  font-size: 24px;
  font-weight: 600;
}

.intro {
  margin: 6px 0 24px;
  color: #606266;
}

.materials {
  width: 100%;
}

.materials :deep(.el-upload) {
  width: 100%;
  margin-top: 12px;
}

.upload-title {
  color: #606266;
}

.field-help {
  margin-top: 6px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}

.material-list {
  margin-top: 12px;
  padding: 0;
  list-style: none;
}

.material-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
}

.material-info {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.file-name {
  overflow-wrap: anywhere;
}

.material-notice {
  margin-top: 10px;
  color: #8a5a13;
  font-size: 13px;
}

.material-notice[data-status='READY'] {
  color: #2e7d32;
}

.material-notice[data-status='ERROR'] {
  color: #b42318;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.job-info {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-top: 20px;
  color: #606266;
  overflow-wrap: anywhere;
}

.error-message,
.result,
.sources {
  margin-top: 20px;
}

.sources {
  overflow-wrap: anywhere;
  font-size: 13px;
}

.sources ul {
  padding-left: 20px;
}

.build-knowledge-button {
  margin-top: 12px;
}

.result label {
  display: block;
  margin-bottom: 8px;
}

@media (max-width: 600px) {
  .crew-form-container {
    padding: 18px;
  }
}
</style>
