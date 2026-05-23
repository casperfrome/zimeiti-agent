import { api } from './client'
import type { PromptOut } from './types'

export const promptsApi = {
  list:   (fn?: string) => api.get<PromptOut[]>(fn ? `/prompts?function_key=${fn}` : '/prompts'),
  create: (body: { function_key: string; name: string; content: string; is_default?: boolean }) =>
    api.post<PromptOut>('/prompts', body),
  update: (id: number, body: { name?: string; content?: string }) =>
    api.put<PromptOut>(`/prompts/${id}`, body),
  remove: (id: number) => api.delete<{ok:boolean}>(`/prompts/${id}`),
  setDefault: (id: number) => api.post<PromptOut>(`/prompts/${id}/set-default`),
}
