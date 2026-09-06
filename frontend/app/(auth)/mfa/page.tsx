'use client'

import { useState, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ShieldCheck } from 'lucide-react'
import { setTokens } from '@/lib/auth'
import { TokenResponse } from '@/lib/types'
import { useAuth } from '@/contexts/auth'

const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_URL ?? 'http://localhost:8001'

function userFromJwt(token: string) {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = parts[1]
    const padded = payload + '=='.slice(0, (4 - (payload.length % 4)) % 4)
    const decoded = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(decoded) as Record<string, unknown>
  } catch {
    return null
  }
}

export default function MfaPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const mfaToken = searchParams.get('token') ?? ''
  const { setUser } = useAuth()

  const [code, setCode] = useState('')
  const [serverError, setServerError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (code.length !== 6) {
      setServerError('Please enter the 6-digit code.')
      return
    }

    setServerError(null)
    setIsSubmitting(true)

    try {
      const res = await fetch(`${AUTH_URL}/auth/mfa/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mfa_token: mfaToken, totp_code: code }),
      })

      const data: unknown = await res.json()

      if (!res.ok) {
        const errData = data as { detail?: string }
        setServerError(errData.detail ?? 'Verification failed. Please try again.')
        setCode('')
        inputRef.current?.focus()
        return
      }

      const tokenData = data as TokenResponse
      setTokens(tokenData.access_token, tokenData.refresh_token)

      const payload = userFromJwt(tokenData.access_token)
      if (payload) {
        setUser({
          id: String(payload.sub ?? payload.id ?? ''),
          email: String(payload.email ?? ''),
          role: (payload.role as 'CONSUMER' | 'ROASTER' | 'ADMIN') ?? 'CONSUMER',
          mfa_enabled: Boolean(payload.mfa_enabled ?? false),
          is_active: Boolean(payload.is_active ?? true),
          created_at: String(payload.created_at ?? ''),
        })
      }

      router.replace('/catalog')
    } catch {
      setServerError('Network error. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleCodeChange(e: React.ChangeEvent<HTMLInputElement>) {
    const value = e.target.value.replace(/\D/g, '').slice(0, 6)
    setCode(value)
  }

  return (
    <div className="min-h-[calc(100vh-56px)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-8">
          <div className="flex flex-col items-center mb-6 text-center">
            <div className="bg-amber-100 rounded-full p-3 mb-3">
              <ShieldCheck className="w-6 h-6 text-amber-800" />
            </div>
            <h1 className="text-2xl font-bold text-stone-900">Two-factor auth</h1>
            <p className="text-stone-500 text-sm mt-1">
              Enter the 6-digit code from your authenticator app
            </p>
          </div>

          {serverError && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg px-4 py-3 text-center">
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <div>
              <label htmlFor="totp_code" className="sr-only">
                Authentication code
              </label>
              <input
                ref={inputRef}
                id="totp_code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="one-time-code"
                value={code}
                onChange={handleCodeChange}
                maxLength={6}
                className="w-full text-center text-3xl font-mono tracking-[0.5em] px-4 py-3 rounded-lg border border-stone-300 text-stone-900 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition"
                placeholder="000000"
                autoFocus
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting || code.length !== 6}
              className="w-full bg-amber-950 hover:bg-amber-900 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
            >
              {isSubmitting ? 'Verifying…' : 'Verify'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
