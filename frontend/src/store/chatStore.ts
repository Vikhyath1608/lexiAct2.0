// src/store/chatStore.ts
import { create } from 'zustand'
import { uuid } from '@/utils/uuid'
import type { Message } from '@/types'
import { chatApi } from '@/services/api'

interface ChatState {
  sessions: string[]; activeSession: string
  messages: Record<string, Message[]>; isTyping: boolean
  setActiveSession: (id: string) => void
  newSession: () => void
  loadSessions: () => Promise<void>
  loadHistory: (sessionId: string) => Promise<void>
  sendMessage: (text: string) => Promise<void>
  clearHistory: () => Promise<void>
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: ['default'], activeSession: 'default',
  messages: { default: [] }, isTyping: false,

  setActiveSession: (id) => set({ activeSession: id }),

  newSession: () => {
    const id = `chat-${Date.now()}`
    set(s => ({ sessions: [...s.sessions, id], activeSession: id, messages: { ...s.messages, [id]: [] } }))
  },

  loadSessions: async () => {
    try {
      const data = await chatApi.getSessions()
      const sessions = data.sessions.length ? data.sessions : ['default']
      set(s => ({ sessions, messages: Object.fromEntries(sessions.map(sid => [sid, s.messages[sid] || []])) }))
    } catch { /* silent */ }
  },

  loadHistory: async (sessionId) => {
    try {
      const data = await chatApi.getHistory(sessionId)
      const messages: Message[] = data.messages.map(m => ({
        id: uuid(), role: m.role as 'user'|'assistant',
        content: m.content, createdAt: new Date(m.created_at),
      }))
      set(s => ({ messages: { ...s.messages, [sessionId]: messages } }))
    } catch { /* silent */ }
  },

  sendMessage: async (text) => {
    const { activeSession } = get()
    const userMsg: Message = { id: uuid(), role: 'user', content: text, createdAt: new Date() }
    set(s => ({
      messages: { ...s.messages, [activeSession]: [...(s.messages[activeSession] || []), userMsg] },
      isTyping: true,
    }))
    try {
      const res = await chatApi.sendMessage({ message: text, session_id: activeSession })
      const botMsg: Message = {
        id: uuid(), role: 'assistant', content: res.response, createdAt: new Date(),
        automationType: res.automation_triggered ? res.automation_type ?? undefined : undefined,
      }
      set(s => ({ messages: { ...s.messages, [activeSession]: [...(s.messages[activeSession] || []), botMsg] } }))
    } catch {
      const errMsg: Message = { id: uuid(), role: 'assistant', content: '⚠️ Something went wrong. Please try again.', createdAt: new Date() }
      set(s => ({ messages: { ...s.messages, [activeSession]: [...(s.messages[activeSession] || []), errMsg] } }))
    } finally { set({ isTyping: false }) }
  },

  clearHistory: async () => {
    const { activeSession } = get()
    await chatApi.clearHistory(activeSession)
    set(s => ({ messages: { ...s.messages, [activeSession]: [] } }))
  },
}))
