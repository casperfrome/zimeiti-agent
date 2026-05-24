import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import Modal from '../components/Modal'
import Select from '../components/Select'
import Spinner from '../components/Spinner'
import { useToast } from '../components/Toast'
import { settingsApi } from '../api/settings'
import type { ModelOut, ModelPurpose, ProviderOut } from '../api/types'

const PURPOSE_GROUPS: { id: ModelPurpose; label: string; desc: string }[] = [
  { id: 'chat',         label: '聊天 LLM',     desc: '用于文案生成 / 润色（DeepSeek、Kimi 等 OpenAI 兼容）' },
  { id: 'image',        label: '文生图',       desc: '用于图片生成（阿里云通义万相）' },
  { id: 'tts',          label: '配音 TTS',     desc: '用于视频合成里的旁白配音（阿里云 CosyVoice）' },
  { id: 'prompt_split', label: '分镜拆分',     desc: '把文案拆成多条配图 prompt（本地 Ollama 或云端 LLM）' },
]

export default function ModelsManager() {
  const toast = useToast()
  const [providers, setProviders] = useState<ProviderOut[]>([])
  const [models, setModels] = useState<ModelOut[]>([])
  const [loading, setLoading] = useState(true)

  const [editKey, setEditKey] = useState<ProviderOut | null>(null)
  const [keyDraft, setKeyDraft] = useState('')
  const [urlDraft, setUrlDraft] = useState('')

  const [addingPurpose, setAddingPurpose] = useState<ModelPurpose | null>(null)
  const [newModel, setNewModel] = useState({ provider_key: '', model_id: '', display_name: '' })

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.all([settingsApi.listProviders(), settingsApi.listModels()]).then(([ps, ms]) => {
      if (active) { setProviders(ps); setModels(ms); setLoading(false) }
    }).catch(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  async function refresh() {
    setLoading(true)
    const [ps, ms] = await Promise.all([settingsApi.listProviders(), settingsApi.listModels()])
    setProviders(ps); setModels(ms); setLoading(false)
  }

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
    if (!addingPurpose || !newModel.provider_key || !newModel.model_id.trim()) {
      toast.push('请填写 provider 和模型 ID', 'err'); return
    }
    try {
      await settingsApi.createModel({
        provider_key: newModel.provider_key,
        model_id: newModel.model_id.trim(),
        display_name: newModel.display_name.trim() || newModel.model_id.trim(),
        purpose: addingPurpose,
      })
      toast.push('已添加')
      setAddingPurpose(null); setNewModel({ provider_key: '', model_id: '', display_name: '' }); refresh()
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
        <p className="mt-1 text-sm text-ink-soft">DeepSeek / Kimi / 阿里云 DashScope / 本地 Ollama 的接入与可用模型。默认模型按用途独立设置。</p>
      </header>

      {/* ===== Providers ===== */}
      <section className="mb-8">
        <div className="label mb-2">Provider 接入</div>
        <div className="space-y-3">
          {providers.map((p) => (
            <motion.div key={p.provider_key} layout className="card flex items-center justify-between p-5">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-base font-semibold text-ink">{p.display_name}</span>
                  {p.has_key
                    ? <span className="chip">已配置</span>
                    : <span className="chip bg-amber-50 text-amber-700">未配置 Key</span>}
                  {p.provider_key === 'ollama' && (
                    <span className="chip">本地服务（无需 Key）</span>
                  )}
                </div>
                <div className="mt-1 text-xs text-ink-mute">
                  Base URL: <span className="text-ink-soft">{p.base_url}</span>
                </div>
                {p.has_key && (
                  <div className="mt-0.5 text-xs text-ink-mute">
                    API Key: <span className="text-ink-soft font-mono">{p.api_key_masked}</span>
                  </div>
                )}
              </div>
              <button className="btn-secondary" onClick={() => { setEditKey(p); setKeyDraft(''); setUrlDraft(p.base_url) }}>编辑</button>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ===== Models by purpose ===== */}
      {PURPOSE_GROUPS.map((g) => {
        const ms = models.filter((m) => m.purpose === g.id)
        return (
          <section key={g.id} className="mb-6">
            <div className="mb-2 flex items-end justify-between">
              <div>
                <div className="text-sm font-semibold text-ink">{g.label}</div>
                <div className="text-xs text-ink-mute">{g.desc}</div>
              </div>
              <button className="btn-ghost" onClick={() => { setAddingPurpose(g.id); setNewModel({ provider_key: providers[0]?.provider_key ?? '', model_id: '', display_name: '' }) }}>
                + 添加模型
              </button>
            </div>
            <div className="card p-4">
              {ms.length === 0 && <div className="py-3 text-sm text-ink-mute">这个用途还没有模型。</div>}
              <div className="space-y-1.5">
                {ms.map((m) => (
                  <motion.div
                    key={m.id}
                    layout
                    className="flex items-center justify-between rounded-ios bg-sage-50/50 px-3.5 py-2.5"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="text-sm font-medium text-ink">{m.display_name}</span>
                      <code className="text-xs text-ink-mute">{m.model_id}</code>
                      <span className="text-xs text-ink-mute">· {m.provider_key}</span>
                      {m.is_default && <span className="chip bg-sage-400 text-white">本用途默认</span>}
                    </div>
                    <div className="flex items-center gap-1">
                      {!m.is_default && <button className="btn-ghost" onClick={() => setDefault(m)}>设为默认</button>}
                      <button className="btn-danger" onClick={() => removeModel(m)}>删除</button>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </section>
        )
      })}

      {/* ===== Provider 编辑弹窗 ===== */}
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
              placeholder={editKey?.has_key ? '留空则保持原 Key' : (editKey?.provider_key === 'ollama' ? '本地服务无需 Key，可留空' : 'sk-...')}
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

      {/* ===== 新建 Model 弹窗 ===== */}
      <Modal
        open={!!addingPurpose}
        onClose={() => setAddingPurpose(null)}
        title={`添加 ${PURPOSE_GROUPS.find((p) => p.id === addingPurpose)?.label ?? ''} 模型`}
        footer={
          <>
            <button className="btn-ghost" onClick={() => setAddingPurpose(null)}>取消</button>
            <button className="btn-primary" onClick={createModel}>添加</button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label mb-1.5 block">Provider</label>
            <Select
              value={newModel.provider_key}
              onChange={(v) => setNewModel({ ...newModel, provider_key: String(v) })}
              options={providers.map((p) => ({ value: p.provider_key, label: p.display_name, hint: p.provider_key }))}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">模型 ID</label>
            <input
              className="input font-mono"
              placeholder="如 wanx2.1-t2i-turbo / cosyvoice-v3-flash / qwen3:8b"
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
