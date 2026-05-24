import { api } from './client'
import type { VideoDetail, VideoSummary } from './types'

export const videosApi = {
  list: (copywriteId?: number) =>
    api.get<VideoSummary[]>(
      copywriteId != null ? `/videos?copywrite_id=${copywriteId}` : '/videos',
    ),
  get: (id: number) => api.get<VideoDetail>(`/videos/${id}`),
  remove: (id: number) => api.delete<{ ok: boolean }>(`/videos/${id}`),
  // POST /videos goes via streamSSE
}

// CosyVoice 已知音色（按模型族）— 用户可在 UI 自定义输入未列出的
export const COSYVOICE_VOICES: Record<string, { id: string; label: string }[]> = {
  v3: [
    { id: 'longanyang',     label: '龙安阳 · 标准男声 (longanyang)' },
    { id: 'longxiaochun',   label: '龙小淳 · 标准女声 (longxiaochun)' },
    { id: 'longjing',       label: '龙婧 · 知性女声 (longjing)' },
    { id: 'longhua',        label: '龙华 · 沉稳男声 (longhua)' },
  ],
  v2: [
    { id: 'longxiaochun_v2', label: '龙小淳 V2 (longxiaochun_v2)' },
    { id: 'longanyang_v2',   label: '龙安阳 V2 (longanyang_v2)' },
  ],
}

export function voicesForModel(modelId: string): { id: string; label: string }[] {
  if (modelId.startsWith('cosyvoice-v3')) return COSYVOICE_VOICES.v3
  if (modelId.startsWith('cosyvoice-v2')) return COSYVOICE_VOICES.v2
  return COSYVOICE_VOICES.v3
}
