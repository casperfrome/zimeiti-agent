import { api } from './client'
import type { BgmOut } from './types'

export const bgmsApi = {
  list: () => api.get<BgmOut[]>('/bgms'),
  upload: (file: File, name?: string) => {
    const fd = new FormData()
    fd.append('file', file)
    if (name) fd.append('name', name)
    return api.postForm<BgmOut>('/bgms', fd)
  },
  rename: (id: number, name: string) => api.put<BgmOut>(`/bgms/${id}`, { name }),
  remove: (id: number) => api.delete<{ ok: boolean }>(`/bgms/${id}`),
}
