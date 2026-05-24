import { api } from './client'
import type { ImageSetDetail, ImageSetSummary, PromptItem } from './types'

export const imageSetsApi = {
  split: (body: { copywrite_id: number; split_model_id?: number; prompt_id?: number }) =>
    api.post<{ prompts: PromptItem[] }>('/image-sets/split', body),
  list: (copywriteId?: number) =>
    api.get<ImageSetSummary[]>(
      copywriteId != null ? `/image-sets?copywrite_id=${copywriteId}` : '/image-sets',
    ),
  get: (id: number) => api.get<ImageSetDetail>(`/image-sets/${id}`),
  remove: (id: number) => api.delete<{ ok: boolean }>(`/image-sets/${id}`),
  // POST /image-sets/generate and /image-sets/{id}/items/{item_id}/regenerate go via streamSSE
}
