// src/services/api.ts
import axios from 'axios'
import type { TokenResponse, User, ChatRequest, ChatResponse, HistoryResponse } from '@/types'

const BASE = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({ baseURL: BASE, withCredentials: true })

// Attach JWT to every request
api.interceptors.request.use(config => {
  const token = localStorage.getItem('lexiact_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh on 401
let refreshing = false
api.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry && !refreshing) {
      original._retry = true
      refreshing = true
      try {
        const r = await axios.post(`${BASE}/auth/refresh`, {}, { withCredentials: true })
        const newToken = r.data.access_token
        localStorage.setItem('lexiact_token', newToken)
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      } catch {
        localStorage.removeItem('lexiact_token')
        window.location.href = '/login'
      } finally {
        refreshing = false
      }
    }
    return Promise.reject(err)
  }
)

export const authApi = {
  register: (d: { username: string; email: string; password: string; full_name?: string }) =>
    api.post('/auth/register', d).then(r => r.data),

  verifyOtp: (d: { user_id: number; otp: string }) =>
    api.post('/auth/verify-otp', d).then(r => r.data),

  resendOtp: (email: string) =>
    api.post('/auth/resend-otp', { email }).then(r => r.data),

  login: (d: { username: string; password: string }) =>
    api.post<TokenResponse>('/auth/login', d).then(r => r.data),

  logout: () => api.post('/auth/logout').then(r => r.data),

  forgotPassword: (email: string) =>
    api.post('/auth/forgot-password', { email }).then(r => r.data),

  resetPassword: (d: { token: string; new_password: string }) =>
    api.post('/auth/reset-password', d).then(r => r.data),

  me: () => api.get<User>('/auth/me').then(r => r.data),

  googleLogin: () => { window.location.href = `${BASE}/auth/oauth/google/login` },
  githubLogin: () => { window.location.href = `${BASE}/auth/oauth/github/login` },
}

export const chatApi = {
  sendMessage: (d: ChatRequest) =>
    api.post<ChatResponse>('/chat/message', d).then(r => r.data),

  getHistory: (sessionId: string, limit = 20, offset = 0) =>
    api.get<HistoryResponse>(`/chat/history?session_id=${encodeURIComponent(sessionId)}&limit=${limit}&offset=${offset}`)
      .then(r => r.data),

  clearHistory: (sessionId: string) =>
    api.delete(`/chat/history?session_id=${encodeURIComponent(sessionId)}`),

  getSessions: (limit = 20, offset = 0) =>
    api.get<{ sessions: string[]; total: number; limit: number; offset: number }>(
      `/chat/sessions?limit=${limit}&offset=${offset}`
    ).then(r => r.data),
}

export const agentApi = {
  getStatus: (sessionId: string) => api.get(`/agent/status/${sessionId}`).then(r => r.data),
  sendInput: (sessionId: string, answer: string) =>
    api.post(`/agent/input/${sessionId}`, { session_id: sessionId, answer }).then(r => r.data),
  terminate: (sessionId: string) => api.delete(`/agent/session/${sessionId}`),
}

export default api
