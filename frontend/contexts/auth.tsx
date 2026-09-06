'use client'

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from 'react'
import { useRouter } from 'next/navigation'
import { User, TokenResponse } from '@/lib/types'
import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
} from '@/lib/auth'

const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_URL ?? 'http://localhost:8001'

interface JwtPayload {
  sub?: string
  email?: string
  role?: string
  mfa_enabled?: boolean
  is_active?: boolean
  created_at?: string
  [key: string]: unknown
}

function decodeJwt(token: string): JwtPayload | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = parts[1]
    const padded = payload + '=='.slice(0, (4 - (payload.length % 4)) % 4)
    const decoded = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(decoded) as JwtPayload
  } catch {
    return null
  }
}

function userFromJwt(token: string): User | null {
  const payload = decodeJwt(token)
  if (!payload) return null

  const id = payload.sub ?? payload.id as string | undefined
  const email = payload.email
  const role = payload.role

  if (!id || !email || !role) return null

  return {
    id: String(id),
    email: String(email),
    role: role as User['role'],
    mfa_enabled: Boolean(payload.mfa_enabled ?? false),
    is_active: Boolean(payload.is_active ?? true),
    created_at: String(payload.created_at ?? ''),
  }
}

type LoginResult =
  | { success: true }
  | { mfaRequired: true; mfaToken: string }
  | { error: string }

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<LoginResult>
  logout: () => Promise<void>
  setUser: (user: User | null) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const token = getAccessToken()
    if (token) {
      const hydrated = userFromJwt(token)
      setUser(hydrated)
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(
    async (email: string, password: string): Promise<LoginResult> => {
      try {
        const res = await fetch(`${AUTH_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })

        const data: unknown = await res.json()

        if (!res.ok) {
          const errData = data as { detail?: string | { msg: string }[] }
          let message = 'Login failed'
          if (typeof errData.detail === 'string') {
            message = errData.detail
          } else if (Array.isArray(errData.detail) && errData.detail.length > 0) {
            message = errData.detail[0].msg
          }
          return { error: message }
        }

        const body = data as
          | TokenResponse
          | { mfa_required: true; mfa_token: string }

        if ('mfa_required' in body && body.mfa_required) {
          return { mfaRequired: true, mfaToken: body.mfa_token }
        }

        const tokenData = body as TokenResponse
        setTokens(tokenData.access_token, tokenData.refresh_token)
        const hydrated = userFromJwt(tokenData.access_token)
        setUser(hydrated)
        return { success: true }
      } catch {
        return { error: 'Network error. Please try again.' }
      }
    },
    []
  )

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken()
    try {
      if (refreshToken) {
        await fetch(`${AUTH_URL}/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
      }
    } catch {
      // Proceed with local logout even if the request fails
    } finally {
      clearTokens()
      setUser(null)
      router.push('/login')
    }
  }, [router])

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
