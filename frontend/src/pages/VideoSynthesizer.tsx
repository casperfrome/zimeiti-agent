import { motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { bgmsApi } from '../api/bgms'
import { mediaUrl, streamSSE } from '../api/client'
import { copywritesApi } from '../api/copywrites'
import { imageSetsApi } from '../api/imageSets'
import { settingsApi } from '../api/settings'
import { videosApi, voicesForModel } from '../api/videos'
import type {
  BgmOut,
  CopywriteSummary,
  ImageSetSummary,
  ModelOut,
  VideoDetail,
  VideoSummary,
} from '../api/types'
import Modal from '../components/Modal'
import Select from '../components/Select'
import Spinner from '../components/Spinner'
import { useToast } from '../components/Toast'

const RATIO_PRESETS: { id: 'portrait_9_16' | 'landscape_16_9' | 'square_1_1'; label: string }[] = [
  { id: 'portrait_9_16',  label: '竖屏 9:16' },
  { id: 'landscape_16_9', label: '横屏 16:9' },
  { id: 'square_1_1',     label: '方形 1:1' },
]

const STAGES = [
  { id: 'prepare_images', label: '处理图片' },
  { id: 'tts',            label: 'AI 配音' },
  { id: 'build',          label: '合成视频' },
  { id: 'done',           label: '完成' },
]

export default function VideoSynthesizer() {
  const toast = useToast()

  // data sources
  const [copywrites, setCopywrites] = useState<CopywriteSummary[]>([])
  const [imageSets, setImageSets] = useState<ImageSetSummary[]>([])
  const [bgms, setBgms] = useState<BgmOut[]>([])
  const [ttsModels, setTtsModels] = useState<ModelOut[]>([])

  // form
  const [copywriteId, setCopywriteId] = useState<number | undefined>()
  const [imageSetId, setImageSetId] = useState<number | undefined>()
  const [bgmId, setBgmId] = useState<number | undefined>()
  const [ttsModelId, setTtsModelId] = useState<number | undefined>()
  const [ttsVoice, setTtsVoice] = useState('longanyang')
  const [ratio, setRatio] = useState<'portrait_9_16' | 'landscape_16_9' | 'square_1_1'>('portrait_9_16')
  const [fps, setFps] = useState(30)
  const [voiceVolume, setVoiceVolume] = useState(1.5)
  const [bgmVolume, setBgmVolume] = useState(0.08)
  const [targetDuration, setTargetDuration] = useState<string>('')
  const [region, setRegion] = useState<'cn' | 'sg'>('cn')
  const [subtitleFontColor, setSubtitleFontColor] = useState('#FFD400')
  const [subtitleStrokeColor, setSubtitleStrokeColor] = useState('#000000')
  const [subtitleAutoSize, setSubtitleAutoSize] = useState(true)
  const [subtitleFontSize, setSubtitleFontSize] = useState(65)

  // runtime
  const [running, setRunning] = useState(false)
  const [currentVideo, setCurrentVideo] = useState<VideoDetail | null>(null)
  const [stage, setStage] = useState<string>('')
  const [logs, setLogs] = useState<string[]>([])
  const [history, setHistory] = useState<VideoSummary[]>([])
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [elapsedMs, setElapsedMs] = useState<number | null>(null)
  const [frameProgress, setFrameProgress] = useState<string | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(false)

  // init
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    let active = true
    Promise.all([
      copywritesApi.list(),
      bgmsApi.list(),
      settingsApi.listModels({ purpose: 'tts' }),
    ]).then(([cs, bs, ms]) => {
      if (!active) return
      setCopywrites(cs)
      setBgms(bs)
      setTtsModels(ms)
      const def = ms.find((m) => m.is_default)
      setTtsModelId(def?.id)
      if (def) {
        const voices = voicesForModel(def.model_id)
        if (voices.length) setTtsVoice(voices[0].id)
      }
    }).catch((e) => { if (active) toast.push(e.message, 'err') })
    return () => { active = false }
  }, [])

  // load image sets when copywrite changes
  useEffect(() => {
    if (copywriteId == null) { setImageSets([]); setImageSetId(undefined); setHistory([]); return }
    let active = true
    imageSetsApi.list(copywriteId).then((sets) => {
      if (!active) return
      const done = sets.filter((s) => s.status === 'done' || s.status === 'partial')
      setImageSets(done)
      setImageSetId(done[0]?.id)
    }).catch(() => { if (active) setImageSets([]) })
    videosApi.list(copywriteId)
      .then((data) => { if (active) setHistory(data) })
      .catch(() => { if (active) setHistory([]) })
    return () => { active = false }
  }, [copywriteId, currentVideo])

  // when tts model changes, update voice options
  useEffect(() => {
    if (ttsModelId == null) return
    const model = ttsModels.find((m) => m.id === ttsModelId)
    if (!model) return
    const voices = voicesForModel(model.model_id)
    if (!voices.some((v) => v.id === ttsVoice)) {
      setTtsVoice(voices[0]?.id ?? '')
    }
  }, [ttsModelId, ttsModels])

  useEffect(() => {
    if (!running || startedAt == null) return
    setElapsedMs(Date.now() - startedAt)
    const timer = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAt)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [running, startedAt])

  const currentBgm = useMemo(() => bgms.find((b) => b.id === bgmId), [bgms, bgmId])
  const voiceOptions = useMemo(() => {
    const model = ttsModels.find((m) => m.id === ttsModelId)
    return model ? voicesForModel(model.model_id) : []
  }, [ttsModelId, ttsModels])
  const ratioSize = useMemo(() => {
    return ratioSizeForPreset(ratio)
  }, [ratio])
  const resultRatioSize = currentVideo ? ratioSizeForPreset(currentVideo.video_ratio_preset) : ratioSize
  const resolvedSubtitleFontSize = subtitleAutoSize
    ? Math.max(28, Math.min(84, Math.round(Math.min(ratioSize.width, ratioSize.height) * 0.06)))
    : subtitleFontSize
  const previewFontSize = Math.max(18, Math.min(34, Math.round(resolvedSubtitleFontSize * 0.42)))
  const previewStrokeWidth = Math.max(1, Math.round(previewFontSize * 0.08))
  const elapsedLabel = elapsedMs == null ? null : formatElapsed(elapsedMs)
  const selectedTtsModel = useMemo(() => {
    return ttsModels.find((m) => m.id === ttsModelId)
  }, [ttsModelId, ttsModels])
  const hasVoiceOptions = voiceOptions.length > 0
  const canStart = copywriteId != null && imageSetId != null && ttsModelId != null && hasVoiceOptions && !!ttsVoice

  async function start() {
    if (copywriteId == null || imageSetId == null) {
      toast.push('请选择文案和图片集', 'err'); return
    }
    if (!hasVoiceOptions || !ttsVoice) {
      toast.push('当前 TTS 模型没有可用系统音色，请选择 CosyVoice V3 或 V2 模型', 'err'); return
    }
    setRunning(true)
    setCurrentVideo(null)
    setStage('')
    setLogs([])
    setFrameProgress(null)
    setPreviewOpen(false)
    const startTime = Date.now()
    setStartedAt(startTime)
    setElapsedMs(0)
    const ctrl = new AbortController(); abortRef.current = ctrl
    const pushLog = (line: string) => {
      if (mountedRef.current) setLogs((arr) => [...arr, line])
    }
    try {
      await streamSSE('/videos', {
        copywrite_id: copywriteId,
        image_set_id: imageSetId,
        bgm_id: bgmId && bgmId > 0 ? bgmId : undefined,
        tts_model_id: ttsModelId,
        tts_voice: ttsVoice,
        video_ratio_preset: ratio,
        fps,
        voice_volume: voiceVolume,
        bgm_volume: bgmVolume,
        target_duration_seconds: targetDuration.trim() ? Number(targetDuration) : undefined,
        region,
        subtitle_font_color: subtitleFontColor,
        subtitle_stroke_color: subtitleStrokeColor,
        subtitle_font_size: subtitleAutoSize ? null : subtitleFontSize,
      }, async (event, data) => {
        if (!mountedRef.current) return
        if (event === 'start') {
          pushLog(`▷ 视频 #${data.video_id} 开始合成…`)
        } else if (event === 'stage') {
          setStage(data.stage)
          if (data.stage === 'build' && data.frame_index != null) {
            setFrameProgress(`${data.frame_index}/${data.frame_total}`)
          }
          if (data.done) {
            pushLog(`✓ ${labelOfStage(data.stage)} 完成${data.voice_duration != null ? ` (配音 ${data.voice_duration.toFixed(2)}s, 语速 ${data.speech_rate}x)` : ''}`)
          } else if (data.frame_index == null) {
            pushLog(`▷ ${labelOfStage(data.stage)}…`)
          }
        } else if (event === 'done') {
          setStage('done')
          setFrameProgress(null)
          const encStr = data.encoding_duration != null
            ? ` (编码耗时 ${data.encoding_duration.toFixed(1)}s)`
            : ''
          pushLog(`✓ 完成：${data.video_path}${encStr}`)
          videosApi.get(data.video_id).then((detail) => {
            if (mountedRef.current) setCurrentVideo(detail)
          }).catch(() => {})
          toast.push('视频已合成')
        } else if (event === 'error') {
          pushLog(`✗ ${data.message}`)
          toast.push(data.message ?? '合成失败', 'err')
        }
      }, ctrl.signal)
    } catch (e: any) {
      if (mountedRef.current && e.name !== 'AbortError') toast.push(e.message, 'err')
    } finally {
      if (mountedRef.current) {
        setRunning(false)
        setElapsedMs(Date.now() - startTime)
      }
    }
  }

  function stop() { abortRef.current?.abort() }

  async function openHistory(v: VideoSummary) {
    try {
      const detail = await videosApi.get(v.id)
      if (!mountedRef.current) return
      setCurrentVideo(detail)
      setLogs([])
      setStage('done')
      setStartedAt(null)
      setElapsedMs(null)
      setPreviewOpen(false)
    } catch (e: any) {
      if (mountedRef.current) toast.push(e.message, 'err')
    }
  }

  async function deleteVideo(v: VideoSummary) {
    if (!confirm('确认删除该视频？')) return
    try {
      await videosApi.remove(v.id)
      if (!mountedRef.current) return
      toast.push('已删除')
      if (currentVideo?.id === v.id) setCurrentVideo(null)
      if (copywriteId != null) {
        videosApi.list(copywriteId).then((data) => {
          if (mountedRef.current) setHistory(data)
        })
      }
    } catch (e: any) {
      if (mountedRef.current) toast.push(e.message, 'err')
    }
  }

  const currentStageIndex = STAGES.findIndex((s) => s.id === stage)

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">视频合成</h1>
        <p className="mt-1 text-sm text-ink-soft">把文案 + 图片集 + BGM 一键合成为带 AI 配音的短视频。</p>
      </header>

      <section className="card p-6">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="label mb-1.5 block">选择文案</label>
            <Select
              value={copywriteId}
              onChange={setCopywriteId}
              options={copywrites.map((c) => ({ value: c.id, label: c.title || `文案 #${c.id}` }))}
              placeholder="未选择"
            />
          </div>
          <div>
            <label className="label mb-1.5 block">图片集</label>
            <Select
              value={imageSetId}
              onChange={setImageSetId}
              options={imageSets.map((s) => ({
                value: s.id,
                label: `#${s.id} · ${s.status} · ${s.size}`,
                hint: new Date(s.created_at + 'Z').toLocaleString(),
              }))}
              placeholder={copywriteId == null ? '请先选文案' : (imageSets.length === 0 ? '该文案还没有可用图片集' : '未选择')}
            />
          </div>
        </div>

        <div className="mt-3">
          <label className="label mb-1.5 block">BGM</label>
          <Select
            value={bgmId}
            onChange={setBgmId}
            options={[
              { value: 0, label: '不使用 BGM' },
              ...bgms.map((b) => ({ value: b.id, label: b.name, hint: b.original_filename })),
            ]}
            placeholder="选一首背景音乐"
          />
          {currentBgm && (
            <audio src={mediaUrl(currentBgm.file_path)} controls className="mt-2 w-full" preload="none" />
          )}
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="label mb-1.5 block">画幅比例</label>
            <div className="flex gap-2">
              {RATIO_PRESETS.map((r) => (
                <button
                  key={r.id}
                  className={`chip cursor-pointer transition-colors ${ratio === r.id ? 'bg-sage-400 text-white' : ''}`}
                  onClick={() => setRatio(r.id)}
                >{r.label}</button>
              ))}
            </div>
          </div>
          <div>
            <label className="label mb-1.5 block">目标时长（秒，留空=按配音长度）</label>
            <input className="input" type="number" placeholder="自动" value={targetDuration} onChange={(e) => setTargetDuration(e.target.value)} />
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="label mb-1.5 block">配音模型 (CosyVoice)</label>
            <Select
              value={ttsModelId}
              onChange={setTtsModelId}
              options={ttsModels.map((m) => ({
                value: m.id,
                label: m.display_name + (m.is_default ? '  ·  默认' : ''),
                hint: m.model_id,
              }))}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">音色</label>
            <Select
              value={ttsVoice}
              onChange={(v) => setTtsVoice(String(v))}
              options={voiceOptions.map((v) => ({ value: v.id, label: v.label }))}
              placeholder={selectedTtsModel?.model_id.startsWith('cosyvoice-v3.5') ? 'V3.5 需要复刻/设计音色，请改用 V3/V2' : '请选择音色'}
            />
            {!hasVoiceOptions && selectedTtsModel?.model_id.startsWith('cosyvoice-v3.5') && (
              <div className="mt-1.5 text-xs text-red-500">
                CosyVoice V3.5 不支持 longanyang 等系统音色。当前页面请选择 CosyVoice V3 或 V2。
              </div>
            )}
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className="label mb-1.5 block">配音音量 ({voiceVolume.toFixed(2)})</label>
            <input type="range" min={0} max={3} step={0.1} value={voiceVolume} onChange={(e) => setVoiceVolume(Number(e.target.value))} className="w-full accent-sage-500" />
          </div>
          <div>
            <label className="label mb-1.5 block">BGM 音量 ({bgmVolume.toFixed(2)})</label>
            <input type="range" min={0} max={1} step={0.01} value={bgmVolume} onChange={(e) => setBgmVolume(Number(e.target.value))} className="w-full accent-sage-500" />
          </div>
          <div>
            <label className="label mb-1.5 block">FPS</label>
            <input className="input" type="number" min={15} max={60} value={fps} onChange={(e) => setFps(Number(e.target.value) || 30)} />
          </div>
        </div>

        <div className="mt-3">
          <label className="label mb-1.5 block">DashScope 区域</label>
          <div className="flex gap-2">
            {(['cn', 'sg'] as const).map((r) => (
              <button
                key={r}
                className={`chip cursor-pointer transition-colors ${region === r ? 'bg-sage-400 text-white' : ''}`}
                onClick={() => setRegion(r)}
              >{r === 'cn' ? '北京 (cn)' : '新加坡 (sg)'}</button>
            ))}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
          <div>
            <div className="label mb-3">字幕样式</div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label className="block">
                <span className="label mb-1.5 block">字体颜色</span>
                <div className="flex items-center gap-2 rounded-ios bg-white px-3 py-2 shadow-inset">
                  <input
                    type="color"
                    value={isHexColor(subtitleFontColor) ? subtitleFontColor : '#FFD400'}
                    onChange={(e) => setSubtitleFontColor(e.target.value.toUpperCase())}
                    className="h-8 w-10 cursor-pointer border-0 bg-transparent p-0"
                  />
                  <input
                    className="min-w-0 flex-1 bg-transparent text-sm text-ink focus:outline-none"
                    value={subtitleFontColor}
                    onChange={(e) => setSubtitleFontColor(e.target.value.toUpperCase())}
                    maxLength={7}
                  />
                </div>
              </label>
              <label className="block">
                <span className="label mb-1.5 block">描边颜色</span>
                <div className="flex items-center gap-2 rounded-ios bg-white px-3 py-2 shadow-inset">
                  <input
                    type="color"
                    value={isHexColor(subtitleStrokeColor) ? subtitleStrokeColor : '#000000'}
                    onChange={(e) => setSubtitleStrokeColor(e.target.value.toUpperCase())}
                    className="h-8 w-10 cursor-pointer border-0 bg-transparent p-0"
                  />
                  <input
                    className="min-w-0 flex-1 bg-transparent text-sm text-ink focus:outline-none"
                    value={subtitleStrokeColor}
                    onChange={(e) => setSubtitleStrokeColor(e.target.value.toUpperCase())}
                    maxLength={7}
                  />
                </div>
              </label>
              <div>
                <span className="label mb-1.5 block">字体大小</span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className={`chip cursor-pointer transition-colors ${subtitleAutoSize ? 'bg-sage-400 text-white' : ''}`}
                    onClick={() => setSubtitleAutoSize(true)}
                  >自适应</button>
                  <button
                    type="button"
                    className={`chip cursor-pointer transition-colors ${!subtitleAutoSize ? 'bg-sage-400 text-white' : ''}`}
                    onClick={() => setSubtitleAutoSize(false)}
                  >自定义</button>
                </div>
                <input
                  className="input mt-2"
                  type="number"
                  min={12}
                  max={240}
                  value={subtitleFontSize}
                  disabled={subtitleAutoSize}
                  onChange={(e) => setSubtitleFontSize(Number(e.target.value) || 65)}
                />
              </div>
            </div>
          </div>
          <div>
            <div className="label mb-3">字幕预览</div>
            <div
              className="flex w-full items-end justify-center rounded-ios bg-black px-4 pb-5 text-center shadow-inset"
              style={{ aspectRatio: `${ratioSize.width} / ${ratioSize.height}` }}
            >
              <div
                className="max-w-full break-words font-semibold leading-snug"
                style={{
                  color: subtitleFontColor,
                  fontSize: previewFontSize,
                  WebkitTextStroke: `${previewStrokeWidth}px ${subtitleStrokeColor}`,
                  textShadow: `0 0 1px ${subtitleStrokeColor}`,
                }}
              >
                这里是字幕预览
              </div>
            </div>
            <div className="mt-1.5 text-xs text-ink-mute">
              输出字号：{subtitleAutoSize ? `${resolvedSubtitleFontSize}px（自适应）` : `${subtitleFontSize}px`}
            </div>
          </div>
        </div>

        <div className="mt-5 flex items-center gap-2">
          {!running ? (
            <button className="btn-primary" onClick={start} disabled={!canStart}>
              ▶ 开始合成
            </button>
          ) : (
            <button className="btn-secondary" onClick={stop}>停止</button>
          )}
        </div>
      </section>

      {/* 进度 + 日志 */}
      {(running || logs.length > 0) && (
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="card mt-5 p-6"
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="label">合成进度</div>
            {elapsedLabel && (
              <div className="rounded-full bg-sage-50 px-2.5 py-1 text-xs font-medium text-ink-soft">
                合成耗时 {elapsedLabel}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {STAGES.map((s, i) => {
              const reached = currentStageIndex >= i
              return (
                <div key={s.id} className="flex flex-1 items-center gap-2">
                  <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs ${
                    reached ? 'bg-sage-400 text-white' : 'bg-sage-100 text-ink-mute'
                  }`}>{i + 1}</div>
                  <div className={`text-xs ${reached ? 'text-ink font-medium' : 'text-ink-mute'}`}>{s.label}</div>
                  {i < STAGES.length - 1 && <div className={`h-px flex-1 ${reached ? 'bg-sage-300' : 'bg-sage-100'}`} />}
                </div>
              )
            })}
          </div>
          {frameProgress && stage === 'build' && (
            <div className="mt-3 text-sm text-ink-soft">
              编码第 {frameProgress} 帧
            </div>
          )}
          <div className="mt-4 max-h-48 overflow-y-auto rounded-ios bg-sage-50/40 p-3 font-mono text-xs leading-6 text-ink-soft">
            {logs.length === 0 && <div className="text-ink-mute">等待启动…</div>}
            {logs.map((l, i) => <div key={i}>{l}</div>)}
          </div>
        </motion.section>
      )}

      {/* 结果 */}
      {currentVideo && currentVideo.video_path && (
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="card mt-5 p-6"
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="label">视频 #{currentVideo.id}</div>
            <div className="text-xs text-ink-mute">
              {currentVideo.video_ratio_preset} · {currentVideo.video_duration?.toFixed(2)}s
            </div>
          </div>
          <button
            type="button"
            onClick={() => setPreviewOpen(true)}
            className="group relative block w-full overflow-hidden rounded-ios bg-black text-left"
            style={{ aspectRatio: `${resultRatioSize.width} / ${resultRatioSize.height}` }}
          >
            {currentVideo.thumbnail_path ? (
              <img
                src={mediaUrl(currentVideo.thumbnail_path)}
                alt={`视频 #${currentVideo.id} 缩略图`}
                className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-sm text-white/70">
                点击播放视频
              </div>
            )}
            <div className="absolute inset-0 flex items-center justify-center bg-black/10 opacity-100 transition-colors group-hover:bg-black/20">
              <span className="rounded-full bg-white/90 px-4 py-2 text-sm font-medium text-ink shadow-float">
                点击播放
              </span>
            </div>
          </button>
          <div className="mt-3 flex items-center gap-2">
            <a
              href={mediaUrl(currentVideo.video_path)}
              download={`video_${currentVideo.id}.mp4`}
              className="btn-secondary"
            >下载 MP4</a>
          </div>
        </motion.section>
      )}

      {currentVideo && currentVideo.video_path && (
        <Modal
          open={previewOpen}
          onClose={() => setPreviewOpen(false)}
          title={`视频 #${currentVideo.id}`}
          widthClass="max-w-[960px]"
        >
          <video
            controls
            autoPlay
            src={mediaUrl(currentVideo.video_path)}
            className="max-h-[78vh] w-full rounded-ios bg-black"
          />
        </Modal>
      )}

      {/* 历史 */}
      {history.length > 0 && (
        <section className="mt-8">
          <div className="label mb-2">本文案的视频</div>
          <div className="space-y-1.5">
            {history.map((v) => (
              <div key={v.id} className="flex items-center justify-between rounded-ios bg-sage-50/50 px-3.5 py-2.5 text-sm">
                <div className="flex items-center gap-3">
                  <span className="font-medium text-ink">#{v.id}</span>
                  <span className="chip">{v.status}</span>
                  <span className="text-xs text-ink-mute">
                    {v.video_duration ? `${v.video_duration.toFixed(2)}s · ` : ''}
                    {new Date(v.created_at + 'Z').toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button className="btn-ghost" onClick={() => openHistory(v)}>查看</button>
                  <button className="btn-danger" onClick={() => deleteVideo(v)}>删除</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function labelOfStage(id: string): string {
  return STAGES.find((s) => s.id === id)?.label ?? id
}

function ratioSizeForPreset(preset: 'portrait_9_16' | 'landscape_16_9' | 'square_1_1') {
  if (preset === 'landscape_16_9') return { width: 1920, height: 1080 }
  if (preset === 'square_1_1') return { width: 1080, height: 1080 }
  return { width: 1080, height: 1920 }
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

function isHexColor(value: string): boolean {
  return /^#[0-9A-Fa-f]{6}$/.test(value)
}
