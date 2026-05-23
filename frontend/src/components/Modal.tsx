import { AnimatePresence, motion } from 'framer-motion'

export default function Modal({
  open, onClose, title, children, footer, widthClass = 'max-w-[520px]',
}: {
  open: boolean
  onClose: () => void
  title?: React.ReactNode
  children: React.ReactNode
  footer?: React.ReactNode
  widthClass?: string
}) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-40 flex items-end sm:items-center justify-center bg-black/30"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            onClick={(e) => e.stopPropagation()}
            initial={{ y: 40, opacity: 0, scale: 0.98 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 30, opacity: 0, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
            className={`w-full ${widthClass} m-4 rounded-sheet bg-surface shadow-float`}
          >
            {title && (
              <div className="border-b border-black/[0.04] px-5 py-4 text-[15px] font-semibold text-ink">
                {title}
              </div>
            )}
            <div className="p-5">{children}</div>
            {footer && (
              <div className="flex justify-end gap-2 border-t border-black/[0.04] px-5 py-3">
                {footer}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
