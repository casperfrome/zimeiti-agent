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

export type ProviderKey = 'deepseek' | 'kimi' | 'alibaba' | 'ollama' | string

export interface ProviderOut {
  provider_key: ProviderKey
  display_name: string
  api_key_masked: string
  has_key: boolean
  base_url: string
}

export type ModelPurpose = 'chat' | 'image' | 'tts' | 'prompt_split'

export interface ModelOut {
  id: number
  provider_key: string
  model_id: string
  display_name: string
  purpose: ModelPurpose
  is_default: boolean
}

// ---------- BGM ----------

export interface BgmOut {
  id: number
  name: string
  file_path: string
  duration_seconds: number | null
  original_filename: string
  created_at: string
}

// ---------- ImageSet ----------

export interface PromptItem {
  index: number
  prompt: string
}

export interface ImageItemOut {
  id: number
  scene_index: number
  image_index: number
  prompt: string
  file_path: string | null
  source_url: string | null
  request_id: string | null
  status: 'pending' | 'done' | 'failed'
  error: string | null
}

export interface ImageSetSummary {
  id: number
  copywrite_id: number
  image_model_id: number | null
  size: string
  n_per_prompt: number
  status: 'pending' | 'running' | 'done' | 'failed' | 'partial'
  dir_path: string
  created_at: string
}

export interface ImageSetDetail extends ImageSetSummary {
  split_model_id: number | null
  negative_prompt: string
  prompt_extend: boolean
  watermark: boolean
  seed: number | null
  error: string | null
  items: ImageItemOut[]
}

// ---------- Video ----------

export interface VideoSummary {
  id: number
  copywrite_id: number
  image_set_id: number
  bgm_id: number | null
  status: 'pending' | 'running' | 'done' | 'failed'
  video_path: string | null
  video_duration: number | null
  created_at: string
}

export interface VideoDetail extends VideoSummary {
  tts_model_id: number | null
  tts_voice: string
  video_ratio_preset: 'portrait_9_16' | 'landscape_16_9' | 'square_1_1'
  fps: number
  voice_volume: number
  bgm_volume: number
  target_duration_seconds: number | null
  region: 'cn' | 'sg'
  voice_path: string | null
  error: string | null
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
