import { AnimatePresence, motion } from 'framer-motion'
import { createContext, useCallback, useContext, useState } from 'react'

type Toast = { id: number; text: string; kind: 'ok' | 'err' }
type Ctx = { push: (text: string, kind?: 'ok' | 'err') => void }

const ToastCtx = createContext<Ctx>({ push: () => {} })
export const useToast = () => useContext(ToastCtx)

let _id = 0

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])

  const push = useCallback((text: string, kind: 'ok' | 'err' = 'ok') => {
    const id = ++_id
    setItems((p) => [...p, { id, text, kind }])
    setTimeout(() => setItems((p) => p.filter((t) => t.id !== id)), 2600)
  }, [])

  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed top-6 right-6 z-50 flex flex-col gap-2">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: -8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.96 }}
              transition={{ type: 'spring', stiffness: 420, damping: 28 }}
              className={`glass pointer-events-auto rounded-ios px-4 py-2.5 text-sm shadow-float ${
                t.kind === 'ok' ? 'text-ink' : 'text-red-600'
              }`}
            >
              {t.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  )
}
