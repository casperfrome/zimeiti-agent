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

  // runtime
  const [running, setRunning] = useState(false)
  const [currentVideo, setCurrentVideo] = useState<VideoDetail | null>(null)
  const [stage, setStage] = useState<string>('')
  const [logs, setLogs] = useState<string[]>([])
  const [history, setHistory] = useState<VideoSummary[]>([])
  const abortRef = useRef<AbortController | null>(null)

  // init
  useEffect(() => {
    Promise.all([
      copywritesApi.list(),
      bgmsApi.list(),
      settingsApi.listModels({ purpose: 'tts' }),
    ]).then(([cs, bs, ms]) => {
      setCopywrites(cs)
      setBgms(bs)
      setTtsModels(ms)
      const def = ms.find((m) => m.is_default)
      setTtsModelId(def?.id)
      if (def) {
        const voices = voicesForModel(def.model_id)
        if (voices.length) setTtsVoice(voices[0].id)
      }
    }).catch((e) => toast.push(e.message, 'err'))
  }, [])

  // load image sets when copywrite changes
  useEffect(() => {
    if (copywriteId == null) { setImageSets([]); setImageSetId(undefined); setHistory([]); return }
    imageSetsApi.list(copywriteId).then((sets) => {
      const done = sets.filter((s) => s.status === 'done' || s.status === 'partial')
      setImageSets(done)
      setImageSetId(done[0]?.id)
    }).catch(() => setImageSets([]))
    videosApi.list(copywriteId).then(setHistory).catch(() => setHistory([]))
  }, [copywriteId, currentVideo])

  // when tts model changes, update voice options
  useEffect(() => {
    if (ttsModelId == null) return
    const model = ttsModels.find((m) => m.id === ttsModelId)
    if (!model) return
    const voices = voicesForModel(model.model_id)
    if (!voices.some((v) => v.id === ttsVoice)) {
      setTtsVoice(voices[0]?.id ?? 'longanyang')
    }
  }, [ttsModelId, ttsModels])

  const currentBgm = useMemo(() => bgms.find((b) => b.id === bgmId), [bgms, bgmId])
  const voiceOptions = useMemo(() => {
    const model = ttsModels.find((m) => m.id === ttsModelId)
    return model ? voicesForModel(model.model_id) : []
  }, [ttsModelId, ttsModels])

  async function start() {
    if (copywriteId == null || imageSetId == null) {
      toast.push('请选择文案和图片集', 'err'); return
    }
    setRunning(true)
    setCurrentVideo(null)
    setStage('')
    setLogs([])
    const ctrl = new AbortController(); abortRef.current = ctrl
    const pushLog = (line: string) => setLogs((arr) => [...arr, line])
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
      }, async (event, data) => {
        if (event === 'start') {
          pushLog(`▷ 视频 #${data.video_id} 开始合成…`)
        } else if (event === 'stage') {
          setStage(data.stage)
          if (data.done) {
            pushLog(`✓ ${labelOfStage(data.stage)} 完成${data.voice_duration != null ? ` (配音 ${data.voice_duration.toFixed(2)}s, 语速 ${data.speech_rate}x)` : ''}`)
          } else {
            pushLog(`▷ ${labelOfStage(data.stage)}…`)
          }
        } else if (event === 'done') {
          setStage('done')
          pushLog(`✓ 完成：${data.video_path} (${data.video_duration?.toFixed(2)}s)`)
          videosApi.get(data.video_id).then(setCurrentVideo).catch(() => {})
          toast.push('视频已合成')
        } else if (event === 'error') {
          pushLog(`✗ ${data.message}`)
          toast.push(data.message ?? '合成失败', 'err')
        }
      }, ctrl.signal)
    } catch (e: any) {
      if (e.name !== 'AbortError') toast.push(e.message, 'err')
    } finally {
      setRunning(false)
    }
  }

  function stop() { abortRef.current?.abort() }

  async function openHistory(v: VideoSummary) {
    try { setCurrentVideo(await videosApi.get(v.id)); setLogs([]); setStage('done') }
    catch (e: any) { toast.push(e.message, 'err') }
  }

  async function deleteVideo(v: VideoSummary) {
    if (!confirm('确认删除该视频？')) return
    try {
      await videosApi.remove(v.id)
      toast.push('已删除')
      if (currentVideo?.id === v.id) setCurrentVideo(null)
      if (copywriteId != null) videosApi.list(copywriteId).then(setHistory)
    } catch (e: any) { toast.push(e.message, 'err') }
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
            />
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

        <div className="mt-5 flex items-center gap-2">
          {!running ? (
            <button className="btn-primary" onClick={start} disabled={copywriteId == null || imageSetId == null}>
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
          <div className="label mb-3">合成进度</div>
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
          <video
            controls
            src={mediaUrl(currentVideo.video_path)}
            className="w-full rounded-ios bg-black"
          />
          <div className="mt-3 flex items-center gap-2">
            <a
              href={mediaUrl(currentVideo.video_path)}
              download={`video_${currentVideo.id}.mp4`}
              className="btn-secondary"
            >下载 MP4</a>
          </div>
        </motion.section>
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
