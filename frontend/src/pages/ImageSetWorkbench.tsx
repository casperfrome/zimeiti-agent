import { motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { mediaUrl, streamSSE } from '../api/client'
import { copywritesApi } from '../api/copywrites'
import { imageSetsApi } from '../api/imageSets'
import { promptsApi } from '../api/prompts'
import { settingsApi } from '../api/settings'
import type {
  CopywriteSummary,
  ImageItemOut,
  ImageSetDetail,
  ImageSetSummary,
  ModelOut,
  PromptItem,
  PromptOut,
} from '../api/types'
import Select from '../components/Select'
import Spinner from '../components/Spinner'
import { useToast } from '../components/Toast'

const SIZE_PRESETS = [
  '1024*1024',
  '1024*1440',
  '1440*1024',
  '720*1280',
  '1280*720',
]

export default function ImageSetWorkbench() {
  const toast = useToast()

  // ---------- data sources ----------
  const [copywrites, setCopywrites] = useState<CopywriteSummary[]>([])
  const [splitModels, setSplitModels] = useState<ModelOut[]>([])
  const [imageModels, setImageModels] = useState<ModelOut[]>([])
  const [splitPrompts, setSplitPrompts] = useState<PromptOut[]>([])

  // ---------- form state ----------
  const [copywriteId, setCopywriteId] = useState<number | undefined>()
  const [splitModelId, setSplitModelId] = useState<number | undefined>()
  const [splitPromptId, setSplitPromptId] = useState<number | undefined>()
  const [imageModelId, setImageModelId] = useState<number | undefined>()
  const [size, setSize] = useState('1024*1024')
  const [nPerPrompt, setNPerPrompt] = useState(1)
  const [negativePrompt, setNegativePrompt] = useState(
    '低清晰度，畸形，文字水印，logo，多余手指，脸部崩坏，过曝，欠曝',
  )
  const [promptExtend, setPromptExtend] = useState(true)
  const [watermark, setWatermark] = useState(false)
  const [seed, setSeed] = useState<string>('')

  // ---------- runtime ----------
  const [splitting, setSplitting] = useState(false)
  const [prompts, setPrompts] = useState<PromptItem[]>([])
  const [generating, setGenerating] = useState(false)
  const [currentSet, setCurrentSet] = useState<ImageSetDetail | null>(null)
  const [items, setItems] = useState<ImageItemOut[]>([])
  const [regenItemId, setRegenItemId] = useState<number | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // ---------- history ----------
  const [history, setHistory] = useState<ImageSetSummary[]>([])

  // ---------- init load ----------
  useEffect(() => {
    let active = true
    Promise.all([
      copywritesApi.list(),
      settingsApi.listModels({ purpose: 'prompt_split' }),
      settingsApi.listModels({ purpose: 'image' }),
      promptsApi.list('image_prompt_split'),
    ]).then(([cs, sm, im, sp]) => {
      if (!active) return
      setCopywrites(cs)
      setSplitModels(sm)
      setImageModels(im)
      setSplitPrompts(sp)
      setSplitModelId(sm.find((m) => m.is_default)?.id)
      setSplitPromptId(sp.find((p) => p.is_default)?.id)
      setImageModelId(im.find((m) => m.is_default)?.id)
    }).catch((e) => toast.push(e.message, 'err'))
    return () => { active = false }
  }, [])

  // Load history for selected copywrite
  useEffect(() => {
    if (copywriteId == null) { setHistory([]); return }
    imageSetsApi.list(copywriteId).then(setHistory).catch(() => setHistory([]))
  }, [copywriteId, currentSet])

  // ---------- handlers ----------
  async function doSplit() {
    if (copywriteId == null) { toast.push('请先选择文案', 'err'); return }
    setSplitting(true)
    try {
      const res = await imageSetsApi.split({
        copywrite_id: copywriteId,
        split_model_id: splitModelId,
        prompt_id: splitPromptId,
      })
      setPrompts(res.prompts)
      toast.push(`已生成 ${res.prompts.length} 条分镜 prompt`)
    } catch (e: any) { toast.push(e.message, 'err') }
    finally { setSplitting(false) }
  }

  function updatePrompt(idx: number, value: string) {
    setPrompts((ps) => ps.map((p, i) => i === idx ? { ...p, prompt: value } : p))
  }
  function addPrompt() {
    setPrompts((ps) => [...ps, { index: ps.length + 1, prompt: '' }])
  }
  function removePrompt(idx: number) {
    setPrompts((ps) =>
      ps.filter((_, i) => i !== idx).map((p, i) => ({ ...p, index: i + 1 })),
    )
  }

  async function startGenerate() {
    if (copywriteId == null) { toast.push('请先选择文案', 'err'); return }
    const clean = prompts.map((p, i) => ({ index: i + 1, prompt: p.prompt.trim() })).filter((p) => p.prompt)
    if (clean.length === 0) { toast.push('至少需要一条非空 prompt', 'err'); return }
    setGenerating(true)
    setCurrentSet(null)
    setItems([])
    const ctrl = new AbortController(); abortRef.current = ctrl
    try {
      await streamSSE('/image-sets/generate', {
        copywrite_id: copywriteId,
        prompts: clean,
        image_model_id: imageModelId,
        split_model_id: splitModelId,
        size,
        n_per_prompt: nPerPrompt,
        negative_prompt: negativePrompt,
        prompt_extend: promptExtend,
        watermark,
        seed: seed.trim() ? Number(seed) : undefined,
      }, async (event, data) => {
        if (event === 'start') {
          // 拉取详情建立空 items 占位
          const detail = await imageSetsApi.get(data.image_set_id)
          setCurrentSet(detail)
          setItems(detail.items)
        } else if (event === 'item') {
          setItems((arr) => arr.map((it) =>
            it.id === data.item_id
              ? { ...it, status: data.status, file_path: data.file_path ?? it.file_path, error: data.error ?? null }
              : it,
          ))
        } else if (event === 'done') {
          toast.push(`生成完成（成功 ${data.ok}，失败 ${data.fail}）`)
          if (currentSet) {
            imageSetsApi.get(currentSet.id).then(setCurrentSet).catch(() => {})
          }
        } else if (event === 'error') {
          toast.push(data.message ?? '生成失败', 'err')
        }
      }, ctrl.signal)
    } catch (e: any) {
      if (e.name !== 'AbortError') toast.push(e.message, 'err')
    } finally {
      setGenerating(false)
    }
  }

  function stop() { abortRef.current?.abort() }

  async function regenerate(item: ImageItemOut) {
    if (!currentSet) return
    setRegenItemId(item.id)
    try {
      await streamSSE(
        `/image-sets/${currentSet.id}/items/${item.id}/regenerate`,
        {},
        (event, data) => {
          if (event === 'done') {
            setItems((arr) => arr.map((it) =>
              it.id === data.item_id
                ? { ...it, status: data.status, file_path: data.file_path ?? null, error: data.error ?? null }
                : it,
            ))
            toast.push(data.status === 'done' ? '已重生' : `重生失败：${data.error}`, data.status === 'done' ? 'ok' : 'err')
          } else if (event === 'error') {
            toast.push(data.message ?? '重生失败', 'err')
          }
        },
      )
    } finally { setRegenItemId(null) }
  }

  async function openHistory(s: ImageSetSummary) {
    try {
      const d = await imageSetsApi.get(s.id)
      setCurrentSet(d)
      setItems(d.items)
      // 把生成参数回填到表单（方便复用/调整）
      setImageModelId(d.image_model_id ?? undefined)
      setSize(d.size)
      setNPerPrompt(d.n_per_prompt)
      setNegativePrompt(d.negative_prompt)
      setPromptExtend(d.prompt_extend)
      setWatermark(d.watermark)
      setSeed(d.seed?.toString() ?? '')
      setPrompts(d.items
        .filter((it, i, arr) => arr.findIndex((x) => x.scene_index === it.scene_index) === i)
        .map((it) => ({ index: it.scene_index, prompt: it.prompt })),
      )
    } catch (e: any) { toast.push(e.message, 'err') }
  }

  async function deleteSet(s: ImageSetSummary) {
    if (!confirm(`确认删除该图片集？文件会一并清掉。`)) return
    try {
      await imageSetsApi.remove(s.id)
      toast.push('已删除')
      if (currentSet?.id === s.id) { setCurrentSet(null); setItems([]) }
      if (copywriteId != null) imageSetsApi.list(copywriteId).then(setHistory)
    } catch (e: any) { toast.push(e.message, 'err') }
  }

  const scenes = useMemo(() => {
    // 按 scene_index 分组
    const map = new Map<number, ImageItemOut[]>()
    for (const it of items) {
      if (!map.has(it.scene_index)) map.set(it.scene_index, [])
      map.get(it.scene_index)!.push(it)
    }
    return Array.from(map.entries()).sort(([a], [b]) => a - b)
  }, [items])

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">图片生成</h1>
        <p className="mt-1 text-sm text-ink-soft">选择一条文案 → AI 分镜（可改）→ 通义万相批量生成配图。</p>
      </header>

      {/* ===== 阶段 A：选文案 + AI 分镜 ===== */}
      <section className="card p-6">
        <div className="label mb-3">阶段 1 · 分镜拆分</div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="label mb-1.5 block">选择文案</label>
            <Select
              value={copywriteId}
              onChange={(v) => { setCopywriteId(v); setPrompts([]); setCurrentSet(null); setItems([]) }}
              options={copywrites.map((c) => ({ value: c.id, label: c.title || `文案 #${c.id}` }))}
              placeholder="未选择"
            />
          </div>
          <div>
            <label className="label mb-1.5 block">分镜模型 (Ollama)</label>
            <Select
              value={splitModelId}
              onChange={setSplitModelId}
              options={splitModels.map((m) => ({
                value: m.id,
                label: m.display_name + (m.is_default ? '  ·  默认' : ''),
                hint: `${m.provider_key} / ${m.model_id}`,
              }))}
            />
          </div>
        </div>

        <div className="mt-3">
          <label className="label mb-1.5 block">分镜 Prompt</label>
          <Select
            value={splitPromptId}
            onChange={setSplitPromptId}
            options={splitPrompts.map((p) => ({
              value: p.id,
              label: p.name + (p.is_default ? '  ·  默认' : ''),
            }))}
          />
        </div>

        <div className="mt-4 flex items-center gap-2">
          <button className="btn-primary" onClick={doSplit} disabled={splitting || copywriteId == null}>
            {splitting ? <><Spinner size={14} /> AI 分镜中…</> : '✨ AI 分镜'}
          </button>
          {copywriteId == null
            ? <span className="text-xs text-amber-600">↑ 请先在上方选择一条文案</span>
            : prompts.length > 0 && <span className="text-xs text-ink-mute">{prompts.length} 条 prompt</span>
          }
        </div>

        {prompts.length > 0 && (
          <div className="mt-4 space-y-2">
            {prompts.map((p, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="mt-2.5 w-6 shrink-0 text-right text-xs font-medium text-ink-mute">{i + 1}.</span>
                <textarea
                  className="textarea min-h-[64px] text-sm leading-6"
                  value={p.prompt}
                  onChange={(e) => updatePrompt(i, e.target.value)}
                />
                <button className="btn-ghost mt-1.5" onClick={() => removePrompt(i)}>×</button>
              </div>
            ))}
            <button className="btn-ghost w-full" onClick={addPrompt}>+ 添加一条 prompt</button>
          </div>
        )}
      </section>

      {/* ===== 阶段 B：生图参数 + 生成 ===== */}
      <section className="card mt-5 p-6">
        <div className="label mb-3">阶段 2 · 生图参数</div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="label mb-1.5 block">文生图模型</label>
            <Select
              value={imageModelId}
              onChange={setImageModelId}
              options={imageModels.map((m) => ({
                value: m.id,
                label: m.display_name + (m.is_default ? '  ·  默认' : ''),
                hint: m.model_id,
              }))}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">分辨率</label>
            <Select
              value={size}
              onChange={(v) => setSize(String(v))}
              options={SIZE_PRESETS.map((s) => ({ value: s, label: s }))}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">每条 prompt 生成张数 (n)</label>
            <input
              className="input"
              type="number"
              min={1}
              max={4}
              value={nPerPrompt}
              onChange={(e) => setNPerPrompt(Math.max(1, Math.min(4, Number(e.target.value) || 1)))}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">随机种子 (seed，可空)</label>
            <input
              className="input"
              type="number"
              placeholder="留空则随机"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-3">
          <label className="label mb-1.5 block">Negative Prompt</label>
          <textarea
            className="textarea min-h-[60px] text-sm leading-6"
            value={negativePrompt}
            onChange={(e) => setNegativePrompt(e.target.value)}
          />
        </div>

        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <label className="flex items-center justify-between gap-4 rounded-ios bg-sage-50/70 px-3.5 py-3 text-sm text-ink-soft">
            <span>
              <span className="font-medium text-ink">智能改写 prompt</span>
              <span className="ml-2 text-xs text-ink-mute">由模型自动优化提示词</span>
            </span>
            <input
              type="checkbox"
              className="h-4 w-4 accent-sage-500"
              checked={promptExtend}
              onChange={(e) => setPromptExtend(e.target.checked)}
            />
          </label>
          <label className="flex items-center justify-between gap-4 rounded-ios bg-sage-50/70 px-3.5 py-3 text-sm text-ink-soft">
            <span>
              <span className="font-medium text-ink">加水印</span>
              <span className="ml-2 text-xs text-ink-mute">"AI 生成" 字样水印</span>
            </span>
            <input
              type="checkbox"
              className="h-4 w-4 accent-sage-500"
              checked={watermark}
              onChange={(e) => setWatermark(e.target.checked)}
            />
          </label>
        </div>

        <div className="mt-5 flex items-center gap-2">
          {!generating ? (
            <button className="btn-primary" onClick={startGenerate} disabled={prompts.length === 0}>
              开始生成（{prompts.length * nPerPrompt} 张）
            </button>
          ) : (
            <button className="btn-secondary" onClick={stop}>停止生成</button>
          )}
          {generating && (
            <span className="flex items-center gap-1.5 text-xs text-ink-mute">
              <Spinner size={14} /> 生成中…
            </span>
          )}
        </div>
      </section>

      {/* ===== 结果网格 ===== */}
      {items.length > 0 && (
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-5"
        >
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">
              图片集 #{currentSet?.id} · {currentSet?.status}
            </h3>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {scenes.map(([sceneIdx, sceneItems]) =>
              sceneItems.map((it) => (
                <motion.div
                  key={it.id}
                  layout
                  className={`card overflow-hidden p-0 ${it.status === 'failed' ? 'ring-2 ring-red-300' : ''}`}
                >
                  <div className="aspect-square bg-sage-50/60">
                    {it.file_path ? (
                      <img src={mediaUrl(it.file_path)} alt={`scene ${sceneIdx}`} className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-xs text-ink-mute">
                        {it.status === 'pending' && '排队中…'}
                        {it.status === 'failed' && '失败'}
                      </div>
                    )}
                  </div>
                  <div className="space-y-1 px-3 py-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-ink">场景 {it.scene_index}-{it.image_index}</span>
                      <button
                        className="btn-ghost text-xs"
                        onClick={() => regenerate(it)}
                        disabled={regenItemId === it.id || generating}
                      >
                        {regenItemId === it.id ? <Spinner size={12} /> : '重生'}
                      </button>
                    </div>
                    <div className="line-clamp-2 text-[11px] text-ink-mute">{it.prompt}</div>
                    {it.error && <div className="text-[11px] text-red-500">⚠ {it.error}</div>}
                  </div>
                </motion.div>
              )),
            )}
          </div>
        </motion.section>
      )}

      {/* ===== 历史 ===== */}
      {history.length > 0 && (
        <section className="mt-8">
          <div className="label mb-2">本文案的历史图片集</div>
          <div className="space-y-1.5">
            {history.map((s) => (
              <div key={s.id} className="flex items-center justify-between rounded-ios bg-sage-50/50 px-3.5 py-2.5 text-sm">
                <div className="flex items-center gap-3">
                  <span className="font-medium text-ink">#{s.id}</span>
                  <span className="chip">{s.status}</span>
                  <span className="text-xs text-ink-mute">{s.size} · n={s.n_per_prompt} · {new Date(s.created_at + 'Z').toLocaleString()}</span>
                </div>
                <div className="flex items-center gap-1">
                  <button className="btn-ghost" onClick={() => openHistory(s)}>查看</button>
                  <button className="btn-danger" onClick={() => deleteSet(s)}>删除</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
