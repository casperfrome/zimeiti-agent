import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { copywritesApi } from '../api/copywrites'
import type { CopywriteSummary } from '../api/types'
import Spinner from '../components/Spinner'
import { useToast } from '../components/Toast'

function relativeTime(iso: string): string {
  const d = new Date(iso + 'Z')
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
  return d.toLocaleDateString()
}

export default function CopywritesList() {
  const toast = useToast()
  const [items, setItems] = useState<CopywriteSummary[] | null>(null)

  async function refresh() {
    try { setItems(await copywritesApi.list()) }
    catch (e: any) { toast.push(e.message, 'err') }
  }
  useEffect(() => { refresh() }, [])

  async function remove(id: number, title: string) {
    if (!confirm(`确认删除文案 "${title}"？`)) return
    try { await copywritesApi.remove(id); toast.push('已删除'); refresh() }
    catch (e: any) { toast.push(e.message, 'err') }
  }

  return (
    <div>
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">我的文案</h1>
          <p className="mt-1 text-sm text-ink-soft">所有由 AI 生成并保存的短视频脚本。</p>
        </div>
        <Link to="/copywrites/new" className="btn-primary">
          + 新建文案
        </Link>
      </header>

      {items === null && (
        <div className="flex items-center gap-2 text-ink-mute"><Spinner /> 加载中…</div>
      )}

      {items && items.length === 0 && (
        <div className="card flex flex-col items-center gap-3 px-8 py-16 text-center">
          <div className="text-4xl">🌱</div>
          <div className="text-base text-ink">还没有文案，去新建一条吧</div>
          <Link to="/copywrites/new" className="btn-primary mt-2">立即创建</Link>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {items?.map((it) => (
          <motion.div
            key={it.id}
            layoutId={`cw-${it.id}`}
            whileHover={{ y: -2 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="card group relative p-5 cursor-pointer"
          >
            <Link to={`/copywrites/${it.id}`} className="absolute inset-0 rounded-sheet" aria-label={it.title}/>
            <div className="flex items-start justify-between gap-3">
              <motion.h3 layoutId={`cw-title-${it.id}`} className="line-clamp-2 text-[15px] font-semibold leading-6 text-ink">
                {it.title}
              </motion.h3>
              <button
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); remove(it.id, it.title) }}
                className="relative z-10 opacity-0 transition-opacity group-hover:opacity-100 btn-danger"
              >
                删除
              </button>
            </div>
            <div className="mt-3 text-xs text-ink-mute">更新于 {relativeTime(it.updated_at)}</div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
