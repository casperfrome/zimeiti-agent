import type { AiSearchStatus, AiUsage } from './types'

export function formatAiUsage(usage?: AiUsage | null) {
  if (!usage) return 'Token 用量暂未返回，费用暂不可估算'
  const cost =
    usage.estimated_cost_cny == null
      ? '未配置价格'
      : `¥${usage.estimated_cost_cny.toFixed(6)}`
  return `Token ${usage.total_tokens}（输入 ${usage.prompt_tokens}，输出 ${usage.completion_tokens}），费用 ${cost}`
}

export function formatSearchStatus(search?: AiSearchStatus | null) {
  if (!search) return ''
  if (!search.enabled) return '联网搜索：关闭'
  if (search.used) return '联网搜索：已开启并注入参考资料'
  return search.warning || '联网搜索：未使用'
}
