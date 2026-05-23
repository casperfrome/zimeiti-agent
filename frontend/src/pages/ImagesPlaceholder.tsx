import { motion } from 'framer-motion'

export default function ImagesPlaceholder() {
  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">图片生成</h1>
        <p className="mt-1 text-sm text-ink-soft">基于文案内容一键生成短视频配图。</p>
      </header>

      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: 'spring', stiffness: 320, damping: 28 }}
        className="card flex flex-col items-center gap-4 px-8 py-20 text-center"
      >
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-sage-100 text-sage-500">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="3"/>
            <circle cx="9" cy="9" r="2"/>
            <path d="m21 15-5-5L5 21"/>
          </svg>
        </div>
        <div>
          <div className="text-lg font-semibold text-ink">敬请期待</div>
          <p className="mt-2 max-w-sm text-sm text-ink-soft">
            该模块将支持基于文案语义生成多张短视频配图，正在打磨中…
          </p>
        </div>
        <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
          <span className="chip">分镜生成</span>
          <span className="chip">封面图</span>
          <span className="chip">风格化滤镜</span>
        </div>
      </motion.div>
    </div>
  )
}
