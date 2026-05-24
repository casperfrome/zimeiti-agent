import { AnimatePresence, motion } from 'framer-motion'
import { Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import { ToastProvider } from './components/Toast'
import BgmLibrary from './pages/BgmLibrary'
import CopywriteDetail from './pages/CopywriteDetail'
import CopywriteNew from './pages/CopywriteNew'
import CopywritesList from './pages/CopywritesList'
import ImageSetWorkbench from './pages/ImageSetWorkbench'
import ModelsManager from './pages/ModelsManager'
import PromptsManager from './pages/PromptsManager'
import VideoSynthesizer from './pages/VideoSynthesizer'

const pageVariants = {
  initial: { opacity: 0, y: 8 },
  enter:   { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.22, 0.61, 0.36, 1] } },
  exit:    { opacity: 0, y: -6, transition: { duration: 0.16 } },
}

export default function App() {
  const location = useLocation()
  return (
    <ToastProvider>
      <Layout>
        <AnimatePresence mode="popLayout">
          <motion.div
            key={location.pathname}
            variants={pageVariants}
            initial="initial"
            animate="enter"
            exit="exit"
          >
            <Routes location={location}>
              <Route path="/"                element={<CopywritesList />} />
              <Route path="/copywrites/new"  element={<CopywriteNew />} />
              <Route path="/copywrites/:id"  element={<CopywriteDetail />} />
              <Route path="/prompts"         element={<PromptsManager />} />
              <Route path="/models"          element={<ModelsManager />} />
              <Route path="/images"          element={<ImageSetWorkbench />} />
              <Route path="/videos"          element={<VideoSynthesizer />} />
              <Route path="/bgms"            element={<BgmLibrary />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </Layout>
    </ToastProvider>
  )
}
