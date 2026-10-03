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
          placeholder="例如：面向年轻通勤人群，为新品制定推广策略并生成社交媒体文案。"
          :disabled="starting"
        />
        <p class="field-help">说明这次希望完成什么，以及目标受众或其他要求。</p>
      </el-form-item>

      <el-form-item label="上传材料">
        <div class="materials">
          <el-alert
            title="材料接入尚未启用"
            description="当前仅可选择和移除文件，材料不会上传或参与分析。未选择材料时，可使用网址和任务目标启动任务。"
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
            :disabled="starting"
            :on-change="handleMaterialChange"
            :on-exceed="handleMaterialExceed"
          >
            <p class="upload-title">拖入材料，或点击选择文件</p>
            <template #tip>
              <p class="field-help">支持 DOCX、PDF、MD、HTML；最多 5 个文件，每个不超过 10 MB。暂不支持旧版 DOC 和扫描件文字识别。</p>
            </template>
          </el-upload>
          <ul v-if="materialFiles.length" class="material-list" aria-label="已选择的材料">
            <li v-for="file in materialFiles" :key="file.uid">
              <div class="material-info">
                <span class="file-name">{{ file.name }}</span>
                <el-tag type="warning" size="small">已选择 · 尚未接入</el-tag>
              </div>
              <el-button
                text
                type="danger"
                :disabled="starting"
                :aria-label="`移除 ${file.name}`"
                @click="removeMaterial(file)"
              >移除</el-button>
            </li>
          </ul>
          <p v-if="materialFiles.length" class="material-notice" role="status">
            这 {{ materialFiles.length }} 个文件尚未接入。若要按当前方式启动，请先移除材料。
          </p>
        </div>
      </el-form-item>

      <div class="actions">
        <el-button
          type="primary"
          :loading="starting"
          :disabled="materialFiles.length > 0 || refreshing"
          @click="startTask"
        >启动任务</el-button>
        <el-button :loading="refreshing" :disabled="!jobId || starting" @click="refreshTask">刷新结果</el-button>
      </div>
    </el-form>

    <div v-if="jobId" class="job-info" role="status">
      <span>任务 ID：{{ jobId }}</span>
      <span>状态：{{ jobStatus }}</span>
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
import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import {
  MATERIAL_ACCEPT,
  MAX_MATERIAL_FILES,
  buildCrewPayload,
  getMaterialError,
  getWebsiteError,
} from '../form-utils.js'

const API_URL = 'http://127.0.0.1:8012/api/crew'
const form = ref({ customer_domain: '', task_goal: '' })
const crewForm = ref(null)
const materialUpload = ref(null)
const materialFiles = ref([])
const starting = ref(false)
const refreshing = ref(false)
const jobId = ref('')
const jobStatus = ref('')
const resultContent = ref('')
const errorMessage = ref('')

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
  }
}

function handleMaterialExceed() {
  ElMessage.warning(`最多选择 ${MAX_MATERIAL_FILES} 个文件，请移除部分材料后重试`)
}

function removeMaterial(file) {
  materialUpload.value.handleRemove(file)
}

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
    const payload = buildCrewPayload(form.value, materialFiles.value)
    const response = await axios.post(API_URL, payload)
    if (!response.data.job_id) throw new Error('Missing job_id')
    jobId.value = response.data.job_id
    jobStatus.value = '已提交'
    resultContent.value = ''
    ElMessage.success('任务已提交，仅使用网址和本次任务目标')
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
.result {
  margin-top: 20px;
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
