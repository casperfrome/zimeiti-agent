import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { promptsApi } from '../api/prompts'
import type { PromptOut } from '../api/types'
import Modal from '../components/Modal'
import Spinner from '../components/Spinner'
import { useToast } from '../components/Toast'

const FUNCTIONS: { key: PromptOut['function_key']; label: string; desc: string }[] = [
  { key: 'copywrite_generate', label: '文案生成', desc: '根据描述生成短视频文案初版' },
  { key: 'copywrite_polish',   label: '文案润色', desc: '基于已有文案进行节奏感和钩子优化' },
]

export default function PromptsManager() {
  const toast = useToast()
  const [tab, setTab] = useState<PromptOut['function_key']>('copywrite_generate')
  const [prompts, setPrompts] = useState<PromptOut[]>([])
  const [loading, setLoading] = useState(true)

  const [editing, setEditing] = useState<PromptOut | null>(null)
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState({ name: '', content: '', is_default: false })

  useEffect(() => {
    let active = true
    setLoading(true)
    promptsApi.list(tab).then((data) => {
      if (active) { setPrompts(data); setLoading(false) }
    }).catch(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [tab])

  async function refresh() {
    setLoading(true)
    setPrompts(await promptsApi.list(tab))
    setLoading(false)
  }

  function openEdit(p: PromptOut) {
    setEditing(p); setDraft({ name: p.name, content: p.content, is_default: p.is_default })
  }
  function openCreate() {
    setCreating(true); setDraft({ name: '', content: '', is_default: false })
  }

  async function save() {
    if (!draft.name.trim() || !draft.content.trim()) { toast.push('名称和内容必填', 'err'); return }
    try {
      if (editing) {
        await promptsApi.update(editing.id, { name: draft.name, content: draft.content })
        toast.push('已保存')
      } else {
        await promptsApi.create({ function_key: tab, name: draft.name, content: draft.content, is_default: draft.is_default })
        toast.push('已新建')
      }
      setEditing(null); setCreating(false); refresh()
    } catch (e: any) { toast.push(e.message, 'err') }
  }

  async function setDefault(p: PromptOut) {
    try { await promptsApi.setDefault(p.id); toast.push(`已设为默认: ${p.name}`); refresh() }
    catch (e: any) { toast.push(e.message, 'err') }
  }

  async function remove(p: PromptOut) {
    if (!confirm(`确认删除 prompt "${p.name}"？`)) return
    try { await promptsApi.remove(p.id); toast.push('已删除'); refresh() }
    catch (e: any) { toast.push(e.message, 'err') }
  }

  const open = !!editing || creating

  return (
    <div>
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">System Prompt</h1>
          <p className="mt-1 text-sm text-ink-soft">每个 AI 功能可以维护多套提示词，调用时可临时切换。</p>
        </div>
        <button className="btn-primary" onClick={openCreate}>
          + 新建 Prompt
        </button>
      </header>

      <div className="relative mb-5 flex gap-1 rounded-ios bg-sage-50 p-1 w-fit">
        {FUNCTIONS.map((f) => (
          <button
            key={f.key}
            onClick={() => setTab(f.key)}
            className={`relative rounded-[10px] px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === f.key ? 'text-ink' : 'text-ink-soft hover:text-ink'
            }`}
          >
            {tab === f.key && (
              <motion.span
                layoutId="prompt-tab"
                className="pointer-events-none absolute inset-0 -z-0 rounded-[10px] bg-white shadow-card"
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              />
            )}
            <span className="relative z-10">{f.label}</span>
          </button>
        ))}
      </div>

      <p className="mb-4 text-xs text-ink-mute">
        {FUNCTIONS.find((f) => f.key === tab)?.desc}
      </p>

      {loading ? (
        <div className="flex items-center gap-2 text-ink-mute"><Spinner /> 加载中…</div>
      ) : (
        <div className="space-y-3">
          {prompts.map((p) => (
            <motion.div key={p.id} layout className="card p-5">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-semibold text-ink">{p.name}</h3>
                  {p.is_default && <span className="chip bg-sage-400 text-white">默认</span>}
                </div>
                <div className="flex items-center gap-1">
                  {!p.is_default && <button className="btn-ghost" onClick={() => setDefault(p)}>设为默认</button>}
                  <button className="btn-ghost" onClick={() => openEdit(p)}>编辑</button>
                  <button className="btn-danger" onClick={() => remove(p)}>删除</button>
                </div>
              </div>
              <p className="whitespace-pre-wrap text-[13.5px] leading-7 text-ink-soft">{p.content}</p>
            </motion.div>
          ))}
          {prompts.length === 0 && (
            <div className="card p-10 text-center text-sm text-ink-mute">还没有 prompt，点右上新建。</div>
          )}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => { setEditing(null); setCreating(false) }}
        title={editing ? '编辑 Prompt' : '新建 Prompt'}
        widthClass="max-w-[640px]"
        footer={
          <>
            <button className="btn-ghost" onClick={() => { setEditing(null); setCreating(false) }}>取消</button>
            <button className="btn-primary" onClick={save}>保存</button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label mb-1.5 block">名称</label>
            <input
              className="input"
              placeholder="例如 ｜ 卖点强调版"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">内容</label>
            <textarea
              className="textarea min-h-[200px]"
              placeholder="给 AI 的系统指令…"
              value={draft.content}
              onChange={(e) => setDraft({ ...draft, content: e.target.value })}
            />
          </div>
          {creating && (
            <label className="flex items-center gap-2 text-sm text-ink-soft">
              <input
                type="checkbox"
                checked={draft.is_default}
                onChange={(e) => setDraft({ ...draft, is_default: e.target.checked })}
                className="h-4 w-4 accent-sage-500"
              />
              新建后设为该功能的默认 prompt
            </label>
          )}
        </div>
      </Modal>
    </div>
  )
}
