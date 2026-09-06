export type UserRole = 'CONSUMER' | 'ROASTER' | 'ADMIN'

export interface User {
  id: string
  email: string
  role: UserRole
  mfa_enabled: boolean
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export type RoastLevel = 'light' | 'medium' | 'medium_dark' | 'dark'

export interface Coffee {
  id: string
  name: string
  roaster_id: string | null
  origin_country: string | null
  roast_level: RoastLevel | null
  flavor_profile: Record<string, unknown> | null
  description: string | null
  is_active: boolean
  created_at: string
}
