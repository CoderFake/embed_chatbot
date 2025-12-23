'use client'

import { useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { authAPI } from '@/lib/auth-api'
import { getErrorMessage } from '@/lib/error-utils';
import { useAuth } from '@/contexts/auth-context'
import { Logo } from '@/components/Logo'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { useLanguage } from '@/contexts/language-context'
import { Lock, Mail, AlertCircle } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { t } = useLanguage()
  const { setTokens } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const normalizedEmail = email.trim().toLowerCase()

    try {
      const response = await authAPI.login({ email: normalizedEmail, password })

      setTokens(response.access_token, response.refresh_token)

      if (typeof window !== 'undefined') {
        localStorage.setItem('user_email', normalizedEmail)
      }

      if (response.force_password_change) {
        router.push('/change-password')
      } else {
        const redirectUrl = searchParams.get('redirect') || '/dashboard'
        router.push(redirectUrl)
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, t('login.errors.default'), t))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-gray-50 px-4 sm:px-6 lg:px-8">
      {/* Language Switcher - Top Right */}
      <div className="fixed top-4 right-4">
        <LanguageSwitcher />
      </div>

      <div className="max-w-md w-full space-y-8">
        <div className="card">
          {/* Logo */}
          <div className="flex justify-center mb-8">
            <Logo variant="full" />
          </div>

          {/* Header */}
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">
              {t('login.title')}
            </h2>
            <p className="text-gray-600">
              {t('login.subtitle')}
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                {t('login.email')}
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field"
                  style={{ paddingLeft: '2.75rem' }}
                  placeholder={t('login.emailPlaceholder')}
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                {t('login.password')}
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field"
                  style={{ paddingLeft: '2.75rem' }}
                  placeholder={t('login.passwordPlaceholder')}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-3 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {t('login.signingIn')}
                </span>
              ) : (
                t('login.signIn')
              )}
            </button>
          </form>

          {/* Forgot Password Link */}
          <div className="mt-4 text-center">
            <Link
              href="/forgot-password"
              className="text-sm text-[var(--color-primary)] hover:text-[var(--color-primary-dark)] hover:underline"
            >
              {t('login.forgotPassword')}
            </Link>
          </div>

          {/* Footer */}
          <div className="mt-6 text-center">
            <p className="text-xs text-gray-500">
              {t('login.footer')}
            </p>
          </div>
        </div>

        {/* Version Info */}
        <div className="text-center">
          <p className="text-sm text-gray-500">
            {t('login.version')}
          </p>
        </div>
      </div>
    </div>
  )
}

