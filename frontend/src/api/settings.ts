import { api } from './client'
import type { ModelOut, ModelPurpose, ProviderOut } from './types'

export const settingsApi = {
  listProviders: () => api.get<ProviderOut[]>('/settings/providers'),
  updateProvider: (key: string, body: { api_key?: string; base_url?: string }) =>
    api.put<ProviderOut>(`/settings/providers/${key}`, body),

  listModels: (filter?: { providerKey?: string; purpose?: ModelPurpose }) => {
    const params = new URLSearchParams()
    if (filter?.providerKey) params.set('provider_key', filter.providerKey)
    if (filter?.purpose) params.set('purpose', filter.purpose)
    const q = params.toString()
    return api.get<ModelOut[]>(q ? `/settings/models?${q}` : '/settings/models')
  },
  createModel: (body: { provider_key: string; model_id: string; display_name: string; purpose: ModelPurpose }) =>
    api.post<ModelOut>('/settings/models', body),
  updateModel: (id: number, body: { model_id?: string; display_name?: string }) =>
    api.put<ModelOut>(`/settings/models/${id}`, body),
  removeModel: (id: number) => api.delete<{ok:boolean}>(`/settings/models/${id}`),
  setDefaultModel: (id: number) => api.post<ModelOut>(`/settings/models/${id}/set-default`),
}
