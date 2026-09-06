import { getAccessToken, getRefreshToken, setTokens, clearTokens } from './auth'

const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_URL ?? 'http://localhost:8001'
const COFFEE_URL = process.env.NEXT_PUBLIC_COFFEE_URL ?? 'http://localhost:8002'

interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false

  try {
    const res = await fetch(`${AUTH_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!res.ok) return false

    const data: TokenResponse = await res.json()
    setTokens(data.access_token, data.refresh_token)
    return true
  } catch {
    return false
  }
}

export async function authFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getAccessToken()

  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(`${AUTH_URL}${path}`, { ...options, headers })

  if (res.status === 401) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      const newToken = getAccessToken()
      if (newToken) {
        headers.set('Authorization', `Bearer ${newToken}`)
      }
      const retryRes = await fetch(`${AUTH_URL}${path}`, { ...options, headers })
      if (retryRes.status === 401) {
        clearTokens()
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      }
      return retryRes
    } else {
      clearTokens()
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
    }
  }

  return res
}

export async function coffeeFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getAccessToken()

  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(`${COFFEE_URL}${path}`, { ...options, headers })

  if (res.status === 401) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      const newToken = getAccessToken()
      if (newToken) {
        headers.set('Authorization', `Bearer ${newToken}`)
      }
      const retryRes = await fetch(`${COFFEE_URL}${path}`, { ...options, headers })
      if (retryRes.status === 401) {
        clearTokens()
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      }
      return retryRes
    } else {
      clearTokens()
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
    }
  }

  return res
}
