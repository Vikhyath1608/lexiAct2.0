// src/pages/ChatPage.tsx
import { useEffect } from 'react'
import { useChatStore } from '@/store/chatStore'
import Sidebar from '@/components/layout/Sidebar'
import ChatWindow from '@/components/chat/ChatWindow'

export default function ChatPage() {
  const { loadSessions, activeSession, loadHistory } = useChatStore()
  useEffect(() => { loadSessions() }, [])
  useEffect(() => { loadHistory(activeSession) }, [activeSession])
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 ml-64">
        <ChatWindow />
      </div>
    </div>
  )
}
