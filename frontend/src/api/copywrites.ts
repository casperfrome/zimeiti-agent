import { api } from './client'
import type { CopywriteDetail, CopywriteSummary } from './types'

export const copywritesApi = {
  list:   ()                          => api.get<CopywriteSummary[]>('/copywrites'),
  get:    (id: number)                => api.get<CopywriteDetail>(`/copywrites/${id}`),
  update: (id: number, body: { content: string; title?: string }) =>
    api.put<CopywriteDetail>(`/copywrites/${id}`, body),
  remove: (id: number)                => api.delete<{ok:boolean}>(`/copywrites/${id}`),
}
