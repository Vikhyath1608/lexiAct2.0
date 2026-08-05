// src/store/authStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { authApi } from '@/services/api'

interface AuthState {
  token: string | null; user: User | null
  isAuthenticated: boolean; isLoading: boolean
  pendingUserId: number | null  // for OTP verification step

  login: (username: string, password: string) => Promise<void>
  register: (d: { username: string; email: string; password: string; full_name?: string }) => Promise<{ user_id: number }>
  verifyOtp: (user_id: number, otp: string) => Promise<void>
  logout: () => Promise<void>
  fetchMe: () => Promise<void>
  setPendingUserId: (id: number | null) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null, user: null, isAuthenticated: false,
      isLoading: false, pendingUserId: null,

      register: async (data) => {
        set({ isLoading: true })
        try {
          const res = await authApi.register(data)
          set({ pendingUserId: res.user_id })
          return { user_id: res.user_id }
        } finally { set({ isLoading: false }) }
      },

      verifyOtp: async (user_id, otp) => {
        set({ isLoading: true })
        try {
          await authApi.verifyOtp({ user_id, otp })
          set({ pendingUserId: null })
        } finally { set({ isLoading: false }) }
      },

      login: async (username, password) => {
        set({ isLoading: true })
        try {
          const data = await authApi.login({ username, password })
          localStorage.setItem('lexiact_token', data.access_token)
          set({ token: data.access_token, isAuthenticated: true })
          await get().fetchMe()
        } finally { set({ isLoading: false }) }
      },

      logout: async () => {
        try { await authApi.logout() } catch { /* ignore */ }
        localStorage.removeItem('lexiact_token')
        set({ token: null, user: null, isAuthenticated: false })
      },

      fetchMe: async () => {
        try {
          const user = await authApi.me()
          set({ user })
        } catch { get().logout() }
      },

      setPendingUserId: (id) => set({ pendingUserId: id }),
    }),
    {
      name: 'lexiact_auth',
      partialize: (s) => ({ token: s.token, isAuthenticated: s.isAuthenticated }),
    }
  )
)
