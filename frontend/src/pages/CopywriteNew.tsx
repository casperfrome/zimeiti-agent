import { motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatAiUsage, formatSearchStatus } from '../api/aiUsage'
import { streamSSE } from '../api/client'
import { promptsApi } from '../api/prompts'
import { settingsApi } from '../api/settings'
import type { ModelOut, PromptOut } from '../api/types'
import Select from '../components/Select'
import Spinner from '../components/Spinner'
import { useToast } from '../components/Toast'

export default function CopywriteNew() {
  const toast = useToast()
  const nav = useNavigate()

  const [desc, setDesc] = useState('')
  const [models, setModels] = useState<ModelOut[]>([])
  const [prompts, setPrompts] = useState<PromptOut[]>([])
  const [modelId, setModelId] = useState<number | undefined>()
  const [promptId, setPromptId] = useState<number | undefined>()
  const [webSearch, setWebSearch] = useState(true)

  const [streaming, setStreaming] = useState(false)
  const [text, setText] = useState('')
  const [usageSummary, setUsageSummary] = useState('')
  const [searchSummary, setSearchSummary] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const outputRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    Promise.all([
      settingsApi.listModels(),
      promptsApi.list('copywrite_generate'),
    ]).then(([ms, ps]) => {
      if (!active) return
      setModels(ms)
      setPrompts(ps)
      setModelId(ms.find((m) => m.is_default)?.id)
      setPromptId(ps.find((p) => p.is_default)?.id)
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight
  }, [text])

  async function start() {
    if (!desc.trim()) {
      toast.push('请先描述要做什么样的文案', 'err')
      return
    }
    setStreaming(true)
    setText('')
    setUsageSummary('')
    setSearchSummary('')
    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      await streamSSE(
        '/copywrites/generate',
        {
          description: desc,
          model_id: modelId,
          prompt_id: promptId,
          enable_web_search: webSearch,
        },
        (event, data) => {
          if (event === 'delta') {
            setText((t) => t + (data.text ?? ''))
          } else if (event === 'search') {
            const summary = formatSearchStatus(data.search ?? data)
            setSearchSummary(summary)
            if (data.warning) toast.push(data.warning, 'err')
          } else if (event === 'done') {
            const usage = formatAiUsage(data.usage)
            const search = formatSearchStatus(data.search)
            setUsageSummary(usage)
            setSearchSummary(search)
            toast.push('已生成并保存。')
            nav(`/copywrites/${data.id}`, { replace: true, state: { usage: data.usage, search: data.search } })
          } else if (event === 'error') {
            toast.push(data.message ?? '生成失败', 'err')
          }
        },
        ctrl.signal,
      )
    } catch (e: any) {
      if (e.name !== 'AbortError') toast.push(e.message, 'err')
    } finally {
      setStreaming(false)
    }
  }

  function stop() {
    abortRef.current?.abort()
  }

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">新建文案</h1>
        <p className="mt-1 text-sm text-ink-soft">描述你想要的短视频内容，AI 会生成初版口播文案。</p>
      </header>

      <div className="card p-6">
        <label className="label mb-2 block">文案描述</label>
        <textarea
          className="textarea min-h-[120px]"
          placeholder="比如：我想推一款主打降噪和续航的无线耳机，目标是上班族通勤场景..."
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          disabled={streaming}
        />

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="label mb-1.5 block">使用模型</label>
            <Select
              value={modelId}
              onChange={(v) => setModelId(v)}
              options={models.map((m) => ({
                value: m.id,
                label: m.display_name + (m.is_default ? '  ·  默认' : ''),
                hint: `${m.provider_key} / ${m.model_id}`,
              }))}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">使用 Prompt</label>
            <Select
              value={promptId}
              onChange={(v) => setPromptId(v)}
              options={prompts.map((p) => ({
                value: p.id,
                label: p.name + (p.is_default ? '  ·  默认' : ''),
              }))}
            />
          </div>
        </div>

        <label className="mt-4 flex items-center justify-between gap-4 rounded-ios bg-sage-50/70 px-3.5 py-3 text-sm text-ink-soft">
          <span>
            <span className="font-medium text-ink">联网搜索</span>
            <span className="ml-2 text-xs text-ink-mute">默认开启，为 AI 补充实时资料</span>
          </span>
          <input
            type="checkbox"
            className="h-4 w-4 accent-sage-500"
            checked={webSearch}
            onChange={(e) => setWebSearch(e.target.checked)}
            disabled={streaming}
          />
        </label>

        <div className="mt-5 flex items-center gap-2">
          {!streaming ? (
            <button className="btn-primary" onClick={start} disabled={!desc.trim()}>
              生成文案
            </button>
          ) : (
            <button className="btn-secondary" onClick={stop}>停止生成</button>
          )}
          {streaming && (
            <span className="flex items-center gap-1.5 text-xs text-ink-mute">
              <Spinner size={14} /> AI 思考中...
            </span>
          )}
        </div>
      </div>

      {(text || streaming) && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
          className="card mt-5 p-6"
        >
          <div className="label mb-2">实时输出</div>
          <div
            ref={outputRef}
            className={`max-h-[420px] overflow-y-auto whitespace-pre-wrap text-[15px] leading-7 text-ink ${streaming ? 'caret' : ''}`}
          >
            {text}
          </div>
          {!streaming && text && (
            <div className="mt-3 space-y-1 text-xs text-ink-mute">
              <div>已自动保存为草稿，正在打开编辑页...</div>
              {usageSummary && <div>{usageSummary}</div>}
              {searchSummary && <div>{searchSummary}</div>}
            </div>
          )}
        </motion.div>
      )}
    </div>
  )
}
