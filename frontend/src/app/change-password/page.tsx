'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/auth-api'
import { Logo } from '@/components/Logo'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { useLanguage } from '@/contexts/language-context'
import { Lock, AlertCircle, CheckCircle } from 'lucide-react'

export default function ChangePasswordPage() {
  const router = useRouter()
  const { t } = useLanguage()
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const validateForm = (): boolean => {
    if (newPassword.length < 8) {
      setError(t('changePassword.errors.passwordTooShort'))
      return false
    }

    if (newPassword !== confirmPassword) {
      setError(t('changePassword.errors.passwordMismatch'))
      return false
    }

    return true
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess(false)

    if (!validateForm()) {
      return
    }

    setLoading(true)

    try {
      await apiClient.post('/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      })

      setSuccess(true)
      
      // Redirect after 2 seconds
      setTimeout(() => {
        router.push('/')
      }, 2000)
    } catch (err: unknown) {
      let errorDetail = '';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { data?: { detail?: string } } };
        errorDetail = axiosError.response?.data?.detail || '';
      }

      if (errorDetail.toLowerCase().includes('incorrect')) {
        setError(t('changePassword.errors.incorrectOldPassword'))
      } else {
        setError(errorDetail || t('changePassword.errors.default'))
      }
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
              {t('changePassword.title')}
            </h2>
            <p className="text-gray-600">
              {t('changePassword.subtitle')}
            </p>
          </div>

          {/* Success Message */}
          {success && (
            <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-green-700">{t('changePassword.success')}</p>
            </div>
          )}

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
              <label htmlFor="oldPassword" className="block text-sm font-medium text-gray-700 mb-2">
                {t('changePassword.oldPassword')}
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400 pointer-events-none" />
                <input
                  id="oldPassword"
                  name="oldPassword"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  className="input-field input-with-icon"
                  placeholder={t('changePassword.oldPasswordPlaceholder')}
                />
              </div>
            </div>

            <div>
              <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700 mb-2">
                {t('changePassword.newPassword')}
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400 pointer-events-none" />
                <input
                  id="newPassword"
                  name="newPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="input-field input-with-icon"
                  placeholder={t('changePassword.newPasswordPlaceholder')}
                  minLength={8}
                />
              </div>
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-2">
                {t('changePassword.confirmPassword')}
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400 pointer-events-none" />
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input-field input-with-icon"
                  placeholder={t('changePassword.confirmPasswordPlaceholder')}
                  minLength={8}
                />
              </div>
            </div>

            {/* Password Requirements */}
            <div className="text-xs text-gray-500">
              {t('changePassword.requirements')}
            </div>

            <button
              type="submit"
              disabled={loading || success}
              className="w-full btn-primary py-3 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {t('changePassword.changingPassword')}
                </span>
              ) : (
                t('changePassword.changePassword')
              )}
            </button>
          </form>
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

