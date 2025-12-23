/**
 * TypeScript types for Authentication API
 * Matches backend schemas exactly
 */

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  force_password_change: boolean
}

export interface RefreshTokenRequest {
  refresh_token: string
}

export interface RefreshTokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface User {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at: string
  updated_at?: string
}

export interface APIError {
  detail: string
  status_code?: number
}

