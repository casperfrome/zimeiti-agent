import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import { useToast } from '../components/Toast'
import { settingsApi } from '../api/settings'
import type { ModelOut, ProviderOut } from '../api/types'

export default function ModelsManager() {
  const toast = useToast()
  const [providers, setProviders] = useState<ProviderOut[]>([])
  const [models, setModels] = useState<ModelOut[]>([])
  const [loading, setLoading] = useState(true)

  const [editKey, setEditKey] = useState<ProviderOut | null>(null)
  const [keyDraft, setKeyDraft] = useState('')
  const [urlDraft, setUrlDraft] = useState('')

  const [addingFor, setAddingFor] = useState<string | null>(null)
  const [newModel, setNewModel] = useState({ model_id: '', display_name: '' })

  async function refresh() {
    setLoading(true)
    const [ps, ms] = await Promise.all([settingsApi.listProviders(), settingsApi.listModels()])
    setProviders(ps); setModels(ms); setLoading(false)
  }
  useEffect(() => { refresh() }, [])

  async function saveKey() {
    if (!editKey) return
    try {
      await settingsApi.updateProvider(editKey.provider_key, {
        api_key: keyDraft || undefined,
        base_url: urlDraft || undefined,
      })
      toast.push('已保存')
      setEditKey(null); refresh()
    } catch (e: any) { toast.push(e.message, 'err') }
  }

  async function createModel() {
    if (!addingFor) return
    if (!newModel.model_id.trim()) { toast.push('模型 ID 不能为空', 'err'); return }
    try {
      await settingsApi.createModel({
        provider_key: addingFor,
        model_id: newModel.model_id.trim(),
        display_name: newModel.display_name.trim() || newModel.model_id.trim(),
      })
      toast.push('已添加')
      setAddingFor(null); setNewModel({ model_id: '', display_name: '' }); refresh()
    } catch (e: any) { toast.push(e.message, 'err') }
  }

  async function setDefault(m: ModelOut) {
    try { await settingsApi.setDefaultModel(m.id); toast.push(`默认模型已切到 ${m.display_name}`); refresh() }
    catch (e: any) { toast.push(e.message, 'err') }
  }

  async function removeModel(m: ModelOut) {
    if (!confirm(`确认删除模型 "${m.display_name}"？`)) return
    try { await settingsApi.removeModel(m.id); toast.push('已删除'); refresh() }
    catch (e: any) { toast.push(e.message, 'err') }
  }

  if (loading) return <div className="flex items-center gap-2 text-ink-mute"><Spinner /> 加载中…</div>

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">模型与 API Key</h1>
        <p className="mt-1 text-sm text-ink-soft">管理 DeepSeek / Kimi 的接入信息和可用模型，调用 AI 时可临时切换。</p>
      </header>

      <div className="space-y-5">
        {providers.map((p) => {
          const ms = models.filter((m) => m.provider_key === p.provider_key)
          return (
            <motion.section
              key={p.provider_key}
              layout
              className="card p-5"
            >
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold">{p.display_name}</h2>
                    {p.has_key
                      ? <span className="chip">已配置</span>
                      : <span className="chip bg-amber-50 text-amber-700">未配置 Key</span>}
                  </div>
                  <div className="mt-1 text-xs text-ink-mute">
                    Base URL: <span className="text-ink-soft">{p.base_url}</span>
                  </div>
                  <div className="mt-0.5 text-xs text-ink-mute">
                    API Key: <span className="text-ink-soft font-mono">{p.api_key_masked || '—'}</span>
                  </div>
                </div>
                <button
                  className="btn-secondary"
                  onClick={() => { setEditKey(p); setKeyDraft(''); setUrlDraft(p.base_url) }}
                >
                  编辑
                </button>
              </div>

              <div className="border-t border-black/[0.04] pt-4">
                <div className="mb-2 flex items-center justify-between">
                  <div className="label">可用模型</div>
                  <button className="btn-ghost" onClick={() => setAddingFor(p.provider_key)}>
                    + 添加模型
                  </button>
                </div>
                <div className="space-y-1.5">
                  {ms.length === 0 && <div className="text-sm text-ink-mute py-2">还没有模型，点上方添加。</div>}
                  {ms.map((m) => (
                    <motion.div
                      key={m.id}
                      layout
                      className="flex items-center justify-between rounded-ios bg-sage-50/50 px-3.5 py-2.5"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="text-sm font-medium text-ink">{m.display_name}</span>
                        <code className="text-xs text-ink-mute">{m.model_id}</code>
                        {m.is_default && (
                          <span className="chip bg-sage-400 text-white">全局默认</span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        {!m.is_default && (
                          <button className="btn-ghost" onClick={() => setDefault(m)}>设为默认</button>
                        )}
                        <button className="btn-danger" onClick={() => removeModel(m)}>删除</button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.section>
          )
        })}
      </div>

      <Modal
        open={!!editKey}
        onClose={() => setEditKey(null)}
        title={`编辑 ${editKey?.display_name}`}
        footer={
          <>
            <button className="btn-ghost" onClick={() => setEditKey(null)}>取消</button>
            <button className="btn-primary" onClick={saveKey}>保存</button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label mb-1.5 block">API Key</label>
            <input
              className="input font-mono"
              type="password"
              placeholder={editKey?.has_key ? '留空则保持原 Key' : 'sk-...'}
              value={keyDraft}
              onChange={(e) => setKeyDraft(e.target.value)}
            />
            <p className="mt-1 text-xs text-ink-mute">仅在本地数据库存储，不会上传到任何远端。</p>
          </div>
          <div>
            <label className="label mb-1.5 block">Base URL</label>
            <input
              className="input"
              value={urlDraft}
              onChange={(e) => setUrlDraft(e.target.value)}
            />
          </div>
        </div>
      </Modal>

      <Modal
        open={!!addingFor}
        onClose={() => setAddingFor(null)}
        title={`为 ${providers.find((p) => p.provider_key === addingFor)?.display_name ?? ''} 添加模型`}
        footer={
          <>
            <button className="btn-ghost" onClick={() => setAddingFor(null)}>取消</button>
            <button className="btn-primary" onClick={createModel}>添加</button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label mb-1.5 block">模型 ID</label>
            <input
              className="input font-mono"
              placeholder={addingFor === 'deepseek' ? 'deepseek-v4-flash' : 'kimi-k2-0711-preview'}
              value={newModel.model_id}
              onChange={(e) => setNewModel({ ...newModel, model_id: e.target.value })}
            />
            <p className="mt-1 text-xs text-ink-mute">调用 API 时实际传入 model 字段的值。</p>
          </div>
          <div>
            <label className="label mb-1.5 block">显示名</label>
            <input
              className="input"
              placeholder="可选，默认与模型 ID 相同"
              value={newModel.display_name}
              onChange={(e) => setNewModel({ ...newModel, display_name: e.target.value })}
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
