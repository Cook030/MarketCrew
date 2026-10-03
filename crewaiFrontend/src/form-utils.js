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

export function buildCrewPayload(form, materials, knowledgeBase) {
  if (materials.length && (!knowledgeBase?.knowledge_base_id || knowledgeBase.status !== 'READY')) {
    throw new Error('请先上传材料，等待知识库处理完成')
  }
  const websiteError = getWebsiteError(form.customer_domain)
  if (websiteError) throw new Error(websiteError)
  if (!form.task_goal.trim()) throw new Error('请输入本次任务目标')
  if (form.task_goal.trim().length > 4000) throw new Error('本次任务目标不得超过 4000 个字符')
  return {
    customer_domain: form.customer_domain.trim(),
    task_goal: form.task_goal.trim(),
    ...(materials.length ? { knowledge_base_id: knowledgeBase.knowledge_base_id } : {}),
  }
}
