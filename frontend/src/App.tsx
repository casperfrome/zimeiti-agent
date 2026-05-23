import { AnimatePresence, motion } from 'framer-motion'
import { Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import { ToastProvider } from './components/Toast'
import CopywriteDetail from './pages/CopywriteDetail'
import CopywriteNew from './pages/CopywriteNew'
import CopywritesList from './pages/CopywritesList'
import ImagesPlaceholder from './pages/ImagesPlaceholder'
import ModelsManager from './pages/ModelsManager'
import PromptsManager from './pages/PromptsManager'

const pageVariants = {
  initial: { opacity: 0, y: 8 },
  enter:   { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.22, 0.61, 0.36, 1] } },
  exit:    { opacity: 0, y: -6, transition: { duration: 0.16 } },
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="enter"
      exit="exit"
      className="h-full"
    >
      {children}
    </motion.div>
  )
}

export default function App() {
  const location = useLocation()
  return (
    <ToastProvider>
      <Layout>
        <AnimatePresence>
          <Routes location={location} key={location.pathname}>
            <Route path="/"                element={<PageShell><CopywritesList /></PageShell>} />
            <Route path="/copywrites/new"  element={<PageShell><CopywriteNew /></PageShell>} />
            <Route path="/copywrites/:id"  element={<PageShell><CopywriteDetail /></PageShell>} />
            <Route path="/prompts"         element={<PageShell><PromptsManager /></PageShell>} />
            <Route path="/models"          element={<PageShell><ModelsManager /></PageShell>} />
            <Route path="/images"          element={<PageShell><ImagesPlaceholder /></PageShell>} />
          </Routes>
        </AnimatePresence>
      </Layout>
    </ToastProvider>
  )
}
