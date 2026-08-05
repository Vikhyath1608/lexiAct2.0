// src/pages/VerifyOtpPage.tsx
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/services/api'
import { ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'

export default function VerifyOtpPage() {
  const [otp, setOtp] = useState('')
  const [resending, setResending] = useState(false)
  const { verifyOtp, isLoading } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()

  const state = location.state as { user_id: number; email: string } | null
  const userId = state?.user_id
  const email = state?.email

  if (!userId) {
    navigate('/register')
    return null
  }

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await verifyOtp(userId, otp)
      toast.success('Account verified! Please log in.')
      navigate('/login')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Verification failed'
      toast.error(msg)
    }
  }

  const handleResend = async () => {
    if (!email) return
    setResending(true)
    try {
      await authApi.resendOtp(email)
      toast.success('New code sent!')
    } catch {
      toast.error('Failed to resend code')
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-accent items-center justify-center mb-4">
            <ShieldCheck size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">Verify Your Email</h1>
          <p className="text-white/50 text-sm mt-2">
            We sent a 6-digit code to<br />
            <span className="text-primary-light">{email}</span>
          </p>
        </div>

        <div className="glass rounded-2xl p-8 shadow-2xl">
          <form onSubmit={handleVerify} className="space-y-4">
            <input
              className="input-base text-center text-2xl tracking-[0.5em] font-mono"
              placeholder="000000"
              value={otp}
              onChange={e => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              required
              autoFocus
            />
            <button type="submit" className="btn-primary w-full" disabled={isLoading || otp.length !== 6}>
              {isLoading ? 'Verifying…' : 'Verify Account'}
            </button>
          </form>

          <p className="text-center text-white/40 text-sm mt-4">
            Didn't receive the code?{' '}
            <button
              onClick={handleResend}
              disabled={resending}
              className="text-primary-light hover:underline disabled:opacity-40"
            >
              {resending ? 'Sending…' : 'Resend'}
            </button>
          </p>

          <p className="text-center text-white/30 text-xs mt-2">
            Code expires in 10 minutes
          </p>
        </div>
      </div>
    </div>
  )
}
