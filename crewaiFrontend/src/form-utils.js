export const MATERIAL_ACCEPT = '.docx,.pdf,.md,.html,.htm'
export const MAX_MATERIAL_FILES = 5
export const MAX_MATERIAL_BYTES = 10 * 1024 * 1024

export function getWebsiteError(value) {
  try {
    const url = new URL(value.trim())
    if (['http:', 'https:'].includes(url.protocol) && url.hostname) return ''
  } catch {
    // Invalid or empty URL; return a validation message below.
  }
  return '请输入以 http:// 或 https:// 开头的有效网址'
}

export function getMaterialError(file) {
  if (!file) return '无法读取文件，请重新选择'
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!MATERIAL_ACCEPT.split(',').includes(extension)) {
    return '请选择 DOCX、PDF、MD 或 HTML 文件'
  }
  if (!file.size) return '文件为空，请选择有内容的材料'
  if (file.size > MAX_MATERIAL_BYTES) return '每个文件不得超过 10 MB'
  return ''
}

export function buildCrewPayload(form, materials) {
  // Until material ingestion exists, never submit a task that silently ignores files.
  if (materials.length) throw new Error('材料尚未接入，请先移除材料')
  const websiteError = getWebsiteError(form.customer_domain)
  if (websiteError) throw new Error(websiteError)
  if (!form.task_goal.trim()) throw new Error('请输入本次任务目标')
  return {
    customer_domain: form.customer_domain.trim(),
    // Keep the existing backend contract until the knowledge-base API is implemented.
    project_description: form.task_goal.trim(),
  }
}
