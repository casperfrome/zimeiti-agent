import { motion } from 'framer-motion'
import { NavLink } from 'react-router-dom'

const groups = [
  {
    title: '内容生产',
    items: [
      { to: '/',                label: '所有文案', icon: ListIcon },
      { to: '/copywrites/new',  label: '新建文案', icon: PlusIcon },
      { to: '/images',          label: '图片生成', icon: ImageIcon },
      { to: '/videos',          label: '视频合成', icon: VideoIcon },
    ],
  },
  {
    title: '素材库',
    items: [
      { to: '/bgms', label: 'BGM',  icon: MusicIcon },
    ],
  },
  {
    title: 'AI 配置',
    items: [
      { to: '/prompts', label: 'Prompt', icon: ChatIcon },
      { to: '/models',  label: '模型与 Key', icon: KeyIcon },
    ],
  },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full">
      <aside className="w-[220px] shrink-0 border-r border-black/[0.04] glass">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-ios bg-sage-400 text-white shadow-card">
            <LeafIcon />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-ink">文案 Studio</div>
            <div className="text-[11px] text-ink-mute">短视频脚本工作台</div>
          </div>
        </div>

        <nav className="px-3 pt-2 space-y-5">
          {groups.map((g) => (
            <div key={g.title}>
              <div className="label px-2 mb-1.5">{g.title}</div>
              <div className="space-y-0.5">
                {g.items.map((it) => (
                  <NavLink
                    key={it.to}
                    to={it.to}
                    end={it.to === '/'}
                    className={({ isActive }) =>
                      `relative flex items-center gap-2.5 rounded-ios px-3 py-2 text-sm transition-colors ${
                        isActive
                          ? 'text-ink font-medium'
                          : 'text-ink-soft hover:text-ink hover:bg-sage-50'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <motion.span
                            layoutId="nav-active"
                            className="absolute inset-0 -z-0 rounded-ios bg-sage-100"
                            transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                          />
                        )}
                        <span className="relative z-10 flex h-5 w-5 items-center justify-center text-ink-soft">
                          <it.icon />
                        </span>
                        <span className="relative z-10">{it.label}</span>
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="relative mx-auto max-w-[960px] px-10 py-10">{children}</div>
      </main>
    </div>
  )
}

/* ---------- icons (inline svg, 18px stroke) ---------- */

function Icon({ children }: { children: React.ReactNode }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  )
}

function LeafIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 4c0 8-6 14-14 14a6 6 0 0 1-2-1c0-8 6-14 14-14 1 0 1.5.4 2 1z"/>
      <path d="M4 20c4-4 8-6 12-8"/>
    </svg>
  )
}
function ListIcon()  { return <Icon><line x1="8" y1="6" x2="20" y2="6"/><line x1="8" y1="12" x2="20" y2="12"/><line x1="8" y1="18" x2="20" y2="18"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></Icon> }
function PlusIcon()  { return <Icon><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></Icon> }
function ChatIcon()  { return <Icon><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></Icon> }
function KeyIcon()   { return <Icon><circle cx="8" cy="15" r="4"/><path d="M10.5 12.5 21 2"/><path d="M17 6l3 3"/><path d="M14 9l2 2"/></Icon> }
function ImageIcon() { return <Icon><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></Icon> }
function VideoIcon() { return <Icon><rect x="2" y="6" width="14" height="12" rx="2"/><path d="m22 8-6 4 6 4z"/></Icon> }
function MusicIcon() { return <Icon><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></Icon> }
