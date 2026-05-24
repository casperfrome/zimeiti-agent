import { motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { bgmsApi } from '../api/bgms'
import { mediaUrl } from '../api/client'
import type { BgmOut } from '../api/types'
import Spinner from '../components/Spinner'
import { useToast } from '../components/Toast'

function fmtDuration(seconds: number | null): string {
  if (!seconds || seconds <= 0) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function BgmLibrary() {
  const toast = useToast()
  const [items, setItems] = useState<BgmOut[] | null>(null)
  const [uploading, setUploading] = useState(false)
  const [renaming, setRenaming] = useState<{ id: number; name: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  async function load() {
    try { setItems(await bgmsApi.list()) }
    catch (e: any) { toast.push(e.message, 'err') }
  }
  useEffect(() => { load() }, [])

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await bgmsApi.upload(file)
      toast.push('已上传')
      load()
    } catch (e: any) { toast.push(e.message, 'err') }
    finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function saveRename() {
    if (!renaming || !renaming.name.trim()) return
    try {
      await bgmsApi.rename(renaming.id, renaming.name.trim())
      toast.push('已重命名')
      setRenaming(null); load()
    } catch (e: any) { toast.push(e.message, 'err') }
  }

  async function remove(b: BgmOut) {
    if (!confirm(`确认删除 "${b.name}"？文件会一并清掉。`)) return
    try { await bgmsApi.remove(b.id); toast.push('已删除'); load() }
    catch (e: any) { toast.push(e.message, 'err') }
  }

  return (
    <div>
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">BGM 库</h1>
          <p className="mt-1 text-sm text-ink-soft">上传背景音乐，视频合成时直接选用。支持 mp3 / wav / m4a / aac / flac / ogg。</p>
        </div>
        <label className={`btn-primary cursor-pointer ${uploading ? 'opacity-60 pointer-events-none' : ''}`}>
          {uploading ? <Spinner size={14} /> : '+ 上传 BGM'}
          <input
            ref={fileRef}
            type="file"
            accept=".mp3,.wav,.m4a,.aac,.flac,.ogg,audio/*"
            className="hidden"
            onChange={onPick}
          />
        </label>
      </header>

      {items === null && <div className="flex items-center gap-2 text-ink-mute"><Spinner /> 加载中…</div>}

      {items && items.length === 0 && (
        <div className="card flex flex-col items-center gap-3 px-8 py-16 text-center">
          <div className="text-4xl">🎵</div>
          <div className="text-base text-ink">还没有 BGM，点右上角上传一首吧</div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {items?.map((b) => (
          <motion.div
            key={b.id}
            layout
            whileHover={{ y: -2 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="card p-5"
          >
            {renaming?.id === b.id ? (
              <div className="flex gap-2">
                <input
                  className="input"
                  value={renaming.name}
                  onChange={(e) => setRenaming({ ...renaming, name: e.target.value })}
                  onKeyDown={(e) => { if (e.key === 'Enter') saveRename(); if (e.key === 'Escape') setRenaming(null) }}
                  autoFocus
                />
                <button className="btn-primary" onClick={saveRename}>保存</button>
                <button className="btn-ghost" onClick={() => setRenaming(null)}>取消</button>
              </div>
            ) : (
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[15px] font-semibold text-ink">{b.name}</div>
                  <div className="mt-1 truncate text-xs text-ink-mute">
                    {b.original_filename} · {fmtDuration(b.duration_seconds)}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button className="btn-ghost" onClick={() => setRenaming({ id: b.id, name: b.name })}>改名</button>
                  <button className="btn-danger" onClick={() => remove(b)}>删除</button>
                </div>
              </div>
            )}
            <audio
              controls
              src={mediaUrl(b.file_path)}
              className="mt-3 w-full"
              preload="none"
            />
          </motion.div>
        ))}
      </div>
    </div>
  )
}
