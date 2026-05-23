import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { formatAiUsage, formatSearchStatus } from '../api/aiUsage'
import { streamSSE } from '../api/client'
import { copywritesApi } from '../api/copywrites'
import { promptsApi } from '../api/prompts'
import { settingsApi } from '../api/settings'
import type { CopywriteDetail as CW, CopywriteVersionOut, ModelOut, PromptOut } from '../api/types'
import Modal from '../components/Modal'
import Select from '../components/Select'
import Spinner from '../components/Spinner'
import { useToast } from '../components/Toast'

export default function CopywriteDetail() {
  const { id } = useParams<{ id: string }>()
  const cid = Number(id)
  const toast = useToast()
  const location = useLocation()

  const [cw, setCw] = useState<CW | null>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)

  const [models, setModels] = useState<ModelOut[]>([])
  const [prompts, setPrompts] = useState<PromptOut[]>([])

  const [genUsageSummary, setGenUsageSummary] = useState('')
  const [versions, setVersions] = useState<CopywriteVersionOut[]>([])

  const [polishOpen, setPolishOpen] = useState(false)
  const [polishModelId, setPolishModelId] = useState<number | undefined>()
  const [polishPromptId, setPolishPromptId] = useState<number | undefined>()
  const [polishWebSearch, setPolishWebSearch] = useState(true)
  const [polishing, setPolishing] = useState(false)
  const [polishedText, setPolishedText] = useState('')
  const [polishUsageSummary, setPolishUsageSummary] = useState('')
  const [polishSearchSummary, setPolishSearchSummary] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    let active = true
    copywritesApi.get(cid).then((c) => { if (active) { setCw(c); setTitle(c.title); setContent(c.content); setVersions(c.versions) } }).catch((e) => { if (active) toast.push(e.message, 'err') })
    Promise.all([settingsApi.listModels(), promptsApi.list('copywrite_polish')]).then(([ms, ps]) => {
      if (!active) return
      setModels(ms); setPrompts(ps)
      setPolishModelId(ms.find((m) => m.is_default)?.id)
      setPolishPromptId(ps.find((p) => p.is_default)?.id)
    })
    const locState = location.state as { usage?: any; search?: any } | null
    if (locState?.usage) {
      const parts = [formatAiUsage(locState.usage), formatSearchStatus(locState.search)].filter(Boolean)
      setGenUsageSummary(parts.join('　'))
    }
    return () => { active = false }
  }, [cid])

  useEffect(() => {
    if (!cw) return
    setDirty(content !== cw.content || title !== cw.title)
  }, [content, title, cw])

  async function save() {
    setSaving(true)
    try {
      const next = await copywritesApi.update(cid, { content, title })
      setCw(next); setDirty(false); toast.push('已保存')
    } catch (e: any) { toast.push(e.message, 'err') }
    finally { setSaving(false) }
  }

  async function startPolish() {
    setPolishOpen(false)
    setPolishing(true); setPolishedText(''); setPolishUsageSummary(''); setPolishSearchSummary('')
    const ctrl = new AbortController(); abortRef.current = ctrl
    try {
      await streamSSE(
        `/copywrites/${cid}/polish`,
        { model_id: polishModelId, prompt_id: polishPromptId, enable_web_search: polishWebSearch },
        (event, data) => {
          if (event === 'delta') setPolishedText((t) => t + (data.text ?? ''))
          else if (event === 'search') {
            const summary = formatSearchStatus(data.search ?? data)
            setPolishSearchSummary(summary)
            if (data.warning) toast.push(data.warning, 'err')
          }
          else if (event === 'done') {
            const usage = formatAiUsage(data.usage)
            const search = formatSearchStatus(data.search)
            setPolishUsageSummary(usage)
            setPolishSearchSummary(search)
            // 刷新版本历史以显示已持久化的 token 数据
            copywritesApi.get(cid).then((c) => { setCw(c); setVersions(c.versions) }).catch((e) => toast.push(e.message, 'err'))
            toast.push('润色完成，新版已自动记录。')
          }
          else if (event === 'error') { toast.push(data.message ?? '润色失败', 'err') }
        },
        ctrl.signal,
      )
    } catch (e: any) {
      if (e.name !== 'AbortError') toast.push(e.message, 'err')
    } finally {
      setPolishing(false)
    }
  }

  function adoptPolish() { setContent(polishedText); setPolishedText(''); setPolishUsageSummary(''); setPolishSearchSummary(''); toast.push('已采用，记得保存') }
  function discardPolish() { setPolishedText(''); setPolishUsageSummary(''); setPolishSearchSummary('') }
  function stopPolish() { abortRef.current?.abort() }

  if (!cw) {
    return <div className="flex items-center gap-2 text-ink-mute"><Spinner /> 加载中…</div>
  }

  const showPolishOverlay = polishing || polishedText

  return (
    <div className="relative">
      <div className="mb-4 flex items-center gap-3">
        <Link to="/" className="btn-ghost">← 返回</Link>
        <div className="text-xs text-ink-mute">创建于 {new Date(cw.created_at + 'Z').toLocaleString()}</div>
      </div>

      <motion.input
        layoutId={`cw-title-${cid}`}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="mb-4 w-full bg-transparent text-2xl font-semibold tracking-tight text-ink outline-none placeholder:text-ink-mute"
        placeholder="未命名文案"
      />

      <div className="mb-4 rounded-ios bg-sage-50/60 px-4 py-3">
        <div className="label mb-1">最初的描述</div>
        <p className="text-sm text-ink-soft">{cw.description}</p>
      </div>

      <motion.div layoutId={`cw-${cid}`} className="card p-5">
        <textarea
          className="textarea min-h-[360px] text-[15.5px] leading-8"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="文案内容…"
        />
      </motion.div>

      {/* 版本历史 */}
      {versions.length > 0 && (
        <div className="mt-6">
          <h3 className="mb-3 text-sm font-semibold text-ink">版本历史</h3>
          <div className="space-y-2">
            {versions.map((v) => {
              const sourceLabel =
                v.source === 'initial' ? 'AI 生成' :
                v.source === 'polish' ? 'AI 润色' :
                '手动编辑'
              return (
                <div key={v.id} className="rounded-ios bg-sage-50/40 px-4 py-3 text-xs text-ink-soft">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-sage-200/60 px-1.5 py-0.5 font-medium text-ink">
                        {sourceLabel}
                      </span>
                      <span>{new Date(v.created_at + 'Z').toLocaleString()}</span>
                    </div>
                    {v.total_tokens != null && (
                      <span className="text-ink-mute">
                        Token {v.total_tokens.toLocaleString()}
                        {v.estimated_cost_cny != null &&
                          `  ·  ¥${v.estimated_cost_cny.toFixed(6)}`}
                      </span>
                    )}
                  </div>
                  {v.model_id && (
                    <div className="mt-1 text-ink-mute/60">
                      {v.provider_key} / {v.model_id}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="sticky bottom-0 mt-4 -mx-10 border-t border-black/[0.05] glass px-10 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs text-ink-mute">
          {dirty
            ? <span className="text-amber-600">● 有未保存修改</span>
            : <span>● 已保存</span>}
          {genUsageSummary && <span className="border-l border-black/10 pl-3">{genUsageSummary}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={() => setPolishOpen(true)} disabled={polishing}>
            ✨ AI 润色
          </button>
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {showPolishOverlay && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-30 flex items-end justify-center bg-black/30 sm:items-center"
          >
            <motion.div
              initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 20, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 380, damping: 30 }}
              className="m-4 w-full max-w-[680px] rounded-sheet bg-surface p-6 shadow-float"
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base font-semibold text-ink">润色预览</span>
                  {polishing && <span className="flex items-center gap-1.5 text-xs text-ink-mute"><Spinner size={12}/> 生成中…</span>}
                </div>
                {polishing && <button className="btn-ghost" onClick={stopPolish}>停止</button>}
              </div>
              <div className={`max-h-[400px] overflow-y-auto whitespace-pre-wrap rounded-ios bg-sage-50/50 p-4 text-[15px] leading-7 text-ink ${polishing ? 'caret' : ''}`}>
                {polishedText || ' '}
              </div>
              {(polishUsageSummary || polishSearchSummary) && (
                <div className="mt-3 space-y-1 text-xs text-ink-mute">
                  {polishUsageSummary && <div>{polishUsageSummary}</div>}
                  {polishSearchSummary && <div>{polishSearchSummary}</div>}
                </div>
              )}
              <div className="mt-4 flex justify-end gap-2">
                <button className="btn-ghost" onClick={discardPolish} disabled={polishing}>放弃</button>
                <button className="btn-primary" onClick={adoptPolish} disabled={polishing || !polishedText}>
                  采用到正文
                </button>
              </div>
              <p className="mt-3 text-xs text-ink-mute">采用后会替换正文，但需手动点「保存」才会入库。</p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <Modal
        open={polishOpen}
        onClose={() => setPolishOpen(false)}
        title="AI 润色"
        footer={
          <>
            <button className="btn-ghost" onClick={() => setPolishOpen(false)}>取消</button>
            <button className="btn-primary" onClick={startPolish}>开始润色</button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label mb-1.5 block">使用模型</label>
            <Select
              value={polishModelId} onChange={setPolishModelId}
              options={models.map((m) => ({
                value: m.id,
                label: m.display_name + (m.is_default ? '  ·  默认' : ''),
                hint: `${m.provider_key} / ${m.model_id}`,
              }))}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">润色 Prompt</label>
            <Select
              value={polishPromptId} onChange={setPolishPromptId}
              options={prompts.map((p) => ({
                value: p.id,
                label: p.name + (p.is_default ? '  ·  默认' : ''),
              }))}
            />
          </div>
          <label className="flex items-center justify-between gap-4 rounded-ios bg-sage-50/70 px-3.5 py-3 text-sm text-ink-soft">
            <span>
              <span className="font-medium text-ink">联网搜索</span>
              <span className="ml-2 text-xs text-ink-mute">默认开启，为 AI 补充实时资料</span>
            </span>
            <input
              type="checkbox"
              className="h-4 w-4 accent-sage-500"
              checked={polishWebSearch}
              onChange={(e) => setPolishWebSearch(e.target.checked)}
              disabled={polishing}
            />
          </label>
        </div>
      </Modal>
    </div>
  )
}
