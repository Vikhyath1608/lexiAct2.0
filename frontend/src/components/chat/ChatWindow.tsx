// src/components/chat/ChatWindow.tsx
import { useRef, useEffect, useState } from 'react'
import { useChatStore } from '@/store/chatStore'
import MessageBubble from './MessageBubble'
import AgentPanel from '../agent/AgentPanel'
import { Send, Trash2, Globe, MessageSquare } from 'lucide-react'
import clsx from 'clsx'

type Mode = 'chat' | 'agent'

export default function ChatWindow() {
  const { activeSession, messages, sendMessage, clearHistory, isTyping } = useChatStore()
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<Mode>('chat')
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const sessionMessages = messages[activeSession] || []

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [sessionMessages, isTyping])

  const handleSend = async () => {
    const text = input.trim()
    if (!text) return
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    await sendMessage(text)
  }

  const autoResize = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }

  const SUGGESTIONS = ['What time is it?', 'Set timer for 5 minutes', 'Tell me a joke', 'Show tech news']

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Topbar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-white/10 bg-black/20 flex-shrink-0">
        <div className="text-sm font-semibold text-white/80">
          {activeSession === 'default' ? 'Chat' : activeSession}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-1 bg-white/5 rounded-xl p-1">
            {([['chat', MessageSquare, 'Chat'], ['agent', Globe, 'Browser Agent']] as [Mode, React.ElementType, string][]).map(([m, Icon, label]) => (
              <button key={m} onClick={() => setMode(m)}
                className={clsx('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                  mode === m ? 'bg-gradient-to-r from-primary to-accent text-white' : 'text-white/50 hover:text-white/80')}>
                <Icon size={12} />{label}
              </button>
            ))}
          </div>
          <button onClick={clearHistory} className="p-2 rounded-lg text-white/30 hover:text-red-400 hover:bg-red-500/10 transition-all" title="Clear">
            <Trash2 size={15} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-4">
        {sessionMessages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-white/30 gap-3">
            <MessageSquare size={40} className="text-primary/40" />
            <div>
              <p className="font-semibold text-white/50 mb-1">Start a conversation</p>
              <p className="text-sm">Ask anything or try a command</p>
              <div className="flex flex-wrap gap-2 mt-4 justify-center">
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => sendMessage(s)}
                    className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-primary/20 text-xs text-white/60 hover:text-primary-light transition-all border border-white/10">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {sessionMessages.map(msg => <MessageBubble key={msg.id} message={msg} />)}

        {isTyping && (
          <div className="flex gap-2 items-start">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary to-accent flex-shrink-0 flex items-center justify-center text-xs font-bold text-white">L</div>
            <div className="glass rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1.5 items-center">
              {[0, 150, 300].map(d => (
                <span key={d} className="w-2 h-2 rounded-full bg-primary/60 animate-pulse-dot" style={{ animationDelay: `${d}ms` }} />
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Agent panel */}
      {mode === 'agent' && <AgentPanel />}

      {/* Input */}
      {mode === 'chat' && (
        <div className="px-6 py-4 border-t border-white/10 bg-black/10 flex-shrink-0">
          <div className="flex gap-3 items-end">
            <textarea ref={textareaRef} className="flex-1 input-base resize-none min-h-[48px] max-h-[140px]"
              placeholder="Message LexiAct… (Enter to send, Shift+Enter for newline)"
              value={input} rows={1}
              onChange={e => { setInput(e.target.value); autoResize(e.target) }}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }} />
            <button onClick={handleSend} disabled={!input.trim()} className="btn-primary px-4 py-3 flex-shrink-0">
              <Send size={18} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
