import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

export interface SelectOption {
  value: string | number
  label: string
  hint?: string
}

export default function Select({
  value, options, onChange, placeholder = '请选择', size = 'md',
}: {
  value: string | number | undefined
  options: SelectOption[]
  onChange: (v: any) => void
  placeholder?: string
  size?: 'sm' | 'md'
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    function close(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const current = options.find((o) => o.value === value)
  const padding = size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-3.5 py-2 text-sm'

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`flex w-full items-center justify-between gap-2 rounded-ios bg-white ${padding} text-ink shadow-inset transition-transform active:scale-[0.99] hover:bg-sage-50/60`}
      >
        <span className={current ? '' : 'text-ink-mute'}>
          {current?.label ?? placeholder}
        </span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-ink-mute">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.14 }}
            className="absolute z-30 mt-1.5 w-full overflow-hidden rounded-ios bg-white shadow-float ring-1 ring-black/[0.04]"
          >
            <div className="max-h-64 overflow-y-auto py-1">
              {options.map((opt) => {
                const active = opt.value === value
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => { onChange(opt.value); setOpen(false) }}
                    className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors ${
                      active ? 'bg-sage-50 text-ink' : 'text-ink-soft hover:bg-sage-50/60'
                    }`}
                  >
                    <div>
                      <div>{opt.label}</div>
                      {opt.hint && <div className="text-[11px] text-ink-mute">{opt.hint}</div>}
                    </div>
                    {active && (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="text-sage-500">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    )}
                  </button>
                )
              })}
              {options.length === 0 && (
                <div className="px-3 py-3 text-sm text-ink-mute">暂无选项</div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
