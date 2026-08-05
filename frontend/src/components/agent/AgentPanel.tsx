// src/components/agent/AgentPanel.tsx
import { useState, useRef } from 'react'
import { useAuthStore } from '@/store/authStore'
import { agentApi } from '@/services/api'
import type { AgentEvent } from '@/types'
import { Play, Send, Globe } from 'lucide-react'
import clsx from 'clsx'
import toast from 'react-hot-toast'

const BASE = import.meta.env.VITE_API_URL || '/api/v1'

export default function AgentPanel() {
  const { token } = useAuthStore()
  const [website, setWebsite] = useState('')
  const [goal, setGoal] = useState('')
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [humanQ, setHumanQ] = useState<string | null>(null)
  const [humanAnswer, setHumanAnswer] = useState('')
  const eventsRef = useRef<HTMLDivElement>(null)

  const addEvent = (ev: AgentEvent) => {
    setEvents(prev => [...prev, ev])
    setTimeout(() => { eventsRef.current?.scrollTo(0, eventsRef.current.scrollHeight) }, 50)
  }

  const runAgent = async () => {
    if (!website || !goal) { toast.error('Enter URL and goal'); return }
    setEvents([]); setHumanQ(null); setIsRunning(true)
    try {
      const res = await fetch(`${BASE}/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ website, goal }),
      })
      const sid = res.headers.get('X-Session-ID')
      if (sid) setSessionId(sid)
      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) return
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const raw = line.slice(5).trim()
          if (!raw || raw.includes('stream_end')) continue
          try {
            const ev: AgentEvent = JSON.parse(raw)
            addEvent(ev)
            if (ev.event === 'human_input') setHumanQ((ev.data?.question as string) || 'Enter your answer')
          } catch { /* skip */ }
        }
      }
    } catch { toast.error('Agent error') }
    finally { setIsRunning(false) }
  }

  const sendHumanInput = async () => {
    if (!sessionId || !humanAnswer.trim()) return
    await agentApi.sendInput(sessionId, humanAnswer)
    setHumanAnswer(''); setHumanQ(null)
    addEvent({ event: 'step', session_id: sessionId, message: `Answer submitted`, data: {} })
  }

  const colors: Record<string, string> = {
    step: 'text-blue-300', action: 'text-green-300', page_change: 'text-yellow-300',
    human_input: 'text-amber-300 font-semibold', error: 'text-red-400', done: 'text-green-400 font-semibold',
  }

  return (
    <div className="mx-6 mb-4 glass rounded-2xl p-5 flex-shrink-0">
      <div className="flex items-center gap-2 mb-4">
        <Globe size={16} className="text-primary-light" />
        <h3 className="text-sm font-semibold text-white/80">Browser Agent — Autonomous Web Automation</h3>
      </div>
      <div className="flex gap-2 flex-wrap">
        <input className="input-base flex-1 min-w-[180px]" placeholder="https://example.com"
          value={website} onChange={e => setWebsite(e.target.value)} disabled={isRunning} />
        <input className="input-base flex-[2] min-w-[220px]" placeholder="Search for iPhone and open first result"
          value={goal} onChange={e => setGoal(e.target.value)} disabled={isRunning}
          onKeyDown={e => e.key === 'Enter' && runAgent()} />
        <button onClick={runAgent} disabled={isRunning}
          className="btn-primary flex items-center gap-2 px-4">
          <Play size={14} />{isRunning ? 'Running…' : 'Run'}
        </button>
      </div>
      {humanQ && (
        <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl">
          <p className="text-amber-300 text-xs font-medium mb-2">🤖 Agent needs input:</p>
          <p className="text-white/80 text-sm mb-3">{humanQ}</p>
          <div className="flex gap-2">
            <input className="input-base flex-1" placeholder="Your answer…"
              value={humanAnswer} onChange={e => setHumanAnswer(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendHumanInput()} autoFocus />
            <button onClick={sendHumanInput} className="btn-primary px-4"><Send size={14} /></button>
          </div>
        </div>
      )}
      {events.length > 0 && (
        <div ref={eventsRef} className="mt-3 max-h-44 overflow-y-auto flex flex-col gap-1 bg-black/20 rounded-xl p-3">
          {events.map((ev, i) => (
            <div key={i} className={clsx('text-[11px] font-mono leading-relaxed', colors[ev.event] || 'text-white/60')}>
              <span className="text-white/20 mr-2">[{ev.event.toUpperCase()}]</span>{ev.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
