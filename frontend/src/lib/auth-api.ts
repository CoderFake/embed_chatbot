/**
 * Auth API Client
 * Handles all API calls with automatic token refresh
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { isPublicEndpoint } from '@/config/api'
import { setCookie, getCookie, deleteCookie } from './cookies'
import type {
  LoginRequest,
  LoginResponse,
  RefreshTokenResponse,
} from './auth-types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

class AuthAPIClient {
  private client: AxiosInstance
  private refreshing: Promise<string> | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    this.client.interceptors.request.use(
      async (config: InternalAxiosRequestConfig) => {
        if (isPublicEndpoint(config.url)) {
          if (config.headers) {
            delete config.headers.Authorization
          }
          return config
        }

        if (this.refreshing && !config.url?.includes('/auth/refresh')) {
          try {
            await this.refreshing
          } catch {
          }
        }

        const token = this.getAccessToken()
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error: unknown) => Promise.reject(error)
    )

    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

        if (error.response?.status === 403) {
          console.error('Access forbidden - insufficient permissions')
          return Promise.reject(error)
        }

        if (error.response?.status === 401 && !originalRequest._retry) {
          if (isPublicEndpoint(originalRequest.url)) {
            return Promise.reject(error)
          }

          if (originalRequest.url?.includes('/auth/refresh')) {
            console.error('Refresh token expired or invalid')
            this.clearTokens()
            if (typeof window !== 'undefined') {
              window.location.href = '/login'
            }
            return Promise.reject(error)
          }

          originalRequest._retry = true

          try {
            console.log('Access token expired, refreshing...')
            const newAccessToken = await this.refreshAccessToken()
            if (newAccessToken && originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
              console.log('Token refreshed successfully, retrying original request')
              return this.client(originalRequest)
            }
          } catch (refreshError) {
            console.error('Failed to refresh token:', refreshError)
            this.clearTokens()
            if (typeof window !== 'undefined') {
              window.location.href = '/login'
            }
            return Promise.reject(refreshError)
          }
        }

        return Promise.reject(error)
      }
    )
  }

  private getAccessToken(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('access_token') || getCookie('access_token')
  }

  private getRefreshToken(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('refresh_token') || getCookie('refresh_token')
  }

  private setTokens(accessToken: string, refreshToken: string) {
    if (typeof window === 'undefined') return
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshToken)
    setCookie('access_token', accessToken, 7)
    setCookie('refresh_token', refreshToken, 7)
  }

  private clearTokens() {
    if (typeof window === 'undefined') return
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    deleteCookie('access_token')
    deleteCookie('refresh_token')
  }

  private async refreshAccessToken(): Promise<string> {
    if (this.refreshing) {
      return this.refreshing
    }

    const refreshToken = this.getRefreshToken()
    if (!refreshToken) {
      throw new Error('No refresh token available')
    }

    this.refreshing = (async () => {
      try {
        const formData = new URLSearchParams()
        formData.append('refresh_token', refreshToken)

        const response = await axios.post<RefreshTokenResponse>(
          `${API_BASE_URL}/auth/refresh`,
          formData,
          {
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          }
        )

        const newAccessToken = response.data.access_token
        const newRefreshToken = response.data.refresh_token

        if (newAccessToken && newRefreshToken) {
          this.setTokens(newAccessToken, newRefreshToken)
          console.log('Tokens rotated successfully (both access and refresh tokens updated)')
        } else if (newAccessToken) {
          if (typeof window !== 'undefined') {
            localStorage.setItem('access_token', newAccessToken)
            setCookie('access_token', newAccessToken, 7)
          }
          console.log('Access token refreshed (refresh token not rotated)')
        }

        return newAccessToken
      } catch (error) {
        console.error('Failed to refresh access token:', error)
        throw error
      } finally {
        this.refreshing = null
      }
    })()

    return this.refreshing
  }

  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await this.client.post<LoginResponse>('/auth/login', credentials)
    const { access_token, refresh_token } = response.data
    this.setTokens(access_token, refresh_token)
    return response.data
  }

  async refresh(refreshToken: string): Promise<RefreshTokenResponse> {
    const formData = new URLSearchParams()
    formData.append('refresh_token', refreshToken)

    const response = await this.client.post<RefreshTokenResponse>(
      '/auth/refresh',
      formData,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    )
    return response.data
  }

  async logout(): Promise<void> {
    try {
      const refreshToken = this.getRefreshToken()
      const accessToken = this.getAccessToken()

      if (!accessToken) {
        console.warn('No access token found, clearing local tokens only')
        this.clearTokens()
        return
      }

      const formData = new URLSearchParams()
      if (refreshToken) {
        formData.append('refresh_token', refreshToken)
      }

      await this.client.post('/auth/logout',
        formData,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/x-www-form-urlencoded',
          }
        }
      )
      console.log('Logout successful, tokens blacklisted')
    } catch (error) {
      console.error('Logout API error:', error)
    } finally {
      this.clearTokens()
    }
  }

  clearLocalTokens() {
    this.clearTokens()
  }

  getClient(): AxiosInstance {
    return this.client
  }
}

export const authAPIClient = new AuthAPIClient()

export const authAPI = {
  login: (credentials: LoginRequest) => authAPIClient.login(credentials),
  refresh: (refreshToken: string) => authAPIClient.refresh(refreshToken),
  logout: () => authAPIClient.logout(),
  clearLocalTokens: () => authAPIClient.clearLocalTokens(),
}

export const apiClient = authAPIClient.getClient()

