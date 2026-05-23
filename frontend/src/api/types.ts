export interface CopywriteSummary {
  id: number
  title: string
  updated_at: string
  total_tokens: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
  estimated_cost_cny: number | null
}

export interface CopywriteVersionOut {
  id: number
  content: string
  source: 'initial' | 'user_edit' | 'polish'
  created_at: string
  provider_key: string | null
  model_id: string | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  prompt_cache_hit_tokens: number | null
  prompt_cache_miss_tokens: number | null
  estimated_cost_cny: number | null
}

export interface CopywriteDetail extends CopywriteSummary {
  description: string
  content: string
  created_at: string
  versions: CopywriteVersionOut[]
}

export interface PromptOut {
  id: number
  function_key: 'copywrite_generate' | 'copywrite_polish'
  name: string
  content: string
  is_default: boolean
  updated_at: string
}

export interface ProviderOut {
  provider_key: 'deepseek' | 'kimi'
  display_name: string
  api_key_masked: string
  has_key: boolean
  base_url: string
}

export interface ModelOut {
  id: number
  provider_key: string
  model_id: string
  display_name: string
  is_default: boolean
}

export interface AiUsage {
  provider_key: string
  model_id: string
  prompt_tokens: number
  prompt_cache_hit_tokens: number
  prompt_cache_miss_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated_cost_cny: number | null
  currency: 'CNY' | null
  pricing_note: string
}

export interface AiSearchStatus {
  enabled: boolean
  used: boolean
  warning: string | null
}
