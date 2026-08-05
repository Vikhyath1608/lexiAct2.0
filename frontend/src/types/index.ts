// src/types/index.ts
export interface User {
  id: number; username: string; email: string
  full_name: string; is_active: boolean; oauth_provider?: string
}
export interface TokenResponse {
  access_token: string; token_type: string
  username: string; full_name: string; user_id: number
}
export interface Message {
  id: string; role: 'user' | 'assistant'
  content: string; createdAt: Date; automationType?: string
}
export interface ConversationEntry { role: string; content: string; created_at: string }
export interface HistoryResponse {
  session_id: string; messages: ConversationEntry[]
  total: number; limit: number; offset: number
}
export interface ChatRequest { message: string; session_id: string }
export interface ChatResponse {
  response: string; session_id: string
  automation_triggered: boolean; automation_type: string | null
}
export interface AgentEvent {
  event: 'step'|'action'|'page_change'|'human_input'|'error'|'done'
  session_id: string; message: string; data: Record<string, unknown>
}
