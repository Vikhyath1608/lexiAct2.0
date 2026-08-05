// src/pages/RegisterPage.tsx
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { Bot, User, Mail, Lock } from 'lucide-react'
import toast from 'react-hot-toast'

export default function RegisterPage() {
  const [form, setForm] = useState({ username: '', email: '', password: '', full_name: '' })
  const { register, isLoading } = useAuthStore()
  const navigate = useNavigate()

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await register(form)
      toast.success('Account created! Check your email for the verification code.')
      navigate('/verify-otp', { state: { user_id: res.user_id, email: form.email } })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Registration failed'
      toast.error(msg)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-accent items-center justify-center mb-4">
            <Bot size={32} className="text-white" />
          </div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary-light to-accent-light bg-clip-text text-transparent">LexiAct</h1>
          <p className="text-white/50 text-sm mt-1">Create your account</p>
        </div>

        <div className="glass rounded-2xl p-8 shadow-2xl">
          <h2 className="text-lg font-semibold mb-6">Register</h2>
          <form onSubmit={handleRegister} className="space-y-4">
            <input className="input-base" placeholder="Full Name" value={form.full_name}
              onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} />
            <div className="relative">
              <User size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/30" />
              <input className="input-base pl-10" placeholder="Username" value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))} required minLength={3} />
            </div>
            <div className="relative">
              <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/30" />
              <input className="input-base pl-10" type="email" placeholder="Email" value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
            </div>
            <div className="relative">
              <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/30" />
              <input className="input-base pl-10" type="password" placeholder="Password (min. 6 chars)"
                value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                required minLength={6} />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={isLoading}>
              {isLoading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>
          <p className="text-center text-white/40 text-sm mt-5">
            Already have an account? <Link to="/login" className="text-primary-light hover:underline">Sign In</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
