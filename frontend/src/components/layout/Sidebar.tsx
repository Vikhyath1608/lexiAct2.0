// src/components/layout/Sidebar.tsx
import { useAuthStore } from '@/store/authStore'
import { useChatStore } from '@/store/chatStore'
import { Bot, PlusCircle, LogOut, MessageSquare } from 'lucide-react'
import clsx from 'clsx'
import { useNavigate } from 'react-router-dom'

export default function Sidebar() {
  const { user, logout } = useAuthStore()
  const { sessions, activeSession, setActiveSession, newSession } = useChatStore()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-64 glass border-r border-white/10 flex flex-col z-10">
      <div className="p-5 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center">
            <Bot size={20} className="text-white" />
          </div>
          <div>
            <h1 className="font-bold text-base text-white">LexiAct</h1>
            <p className="text-white/40 text-xs">{user?.full_name || user?.username || 'User'}</p>
          </div>
        </div>
        {user?.oauth_provider && (
          <div className="mt-2 text-[10px] text-primary-light bg-primary/10 rounded-full px-2 py-0.5 w-fit capitalize">
            via {user.oauth_provider}
          </div>
        )}
      </div>

      <div className="p-3">
        <button onClick={newSession}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl border border-dashed border-primary/30 text-primary-light hover:bg-primary/10 text-sm font-medium transition-all">
          <PlusCircle size={16} /> New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-1">
        <p className="text-[10px] uppercase tracking-widest text-white/30 px-2 mb-2">Sessions</p>
        <div className="flex flex-col gap-1">
          {sessions.map(sid => (
            <button key={sid} onClick={() => setActiveSession(sid)}
              className={clsx(
                'flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm text-left transition-all truncate',
                sid === activeSession ? 'bg-primary/20 text-white' : 'text-white/50 hover:bg-white/5 hover:text-white/80'
              )}>
              <MessageSquare size={14} className="flex-shrink-0" />
              <span className="truncate">{sid === 'default' ? 'Default Chat' : sid}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="p-3 border-t border-white/10">
        <button onClick={handleLogout}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500/20 text-sm transition-all">
          <LogOut size={15} /> Sign Out
        </button>
      </div>
    </aside>
  )
}
