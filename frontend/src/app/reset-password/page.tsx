'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/auth-api'
import { getErrorMessage } from '@/lib/error-utils'
import { Logo } from '@/components/Logo'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { useLanguage } from '@/contexts/language-context'
import { Lock, AlertCircle, CheckCircle } from 'lucide-react'

export default function ResetPasswordPage() {
    const router = useRouter()
    const { t } = useLanguage()
    const [token, setToken] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [error, setError] = useState('')
    const [success, setSuccess] = useState(false)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        // Get token from URL hash
        if (typeof window !== 'undefined') {
            const hash = window.location.hash.substring(1)
            const params = new URLSearchParams(hash)
            const tokenParam = params.get('token')
            if (tokenParam) {
                setToken(tokenParam)
            } else {
                setError(t('resetPassword.invalidLink'))
            }
        }
    }, [t])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')

        if (password !== confirmPassword) {
            setError(t('changePassword.errors.passwordMismatch'))
            return
        }

        if (password.length < 8) {
            setError(t('changePassword.errors.passwordTooShort'))
            return
        }

        if (!token) {
            setError(t('resetPassword.invalidLink'))
            return
        }

        setLoading(true)

        try {
            await apiClient.post('/auth/reset-password', {
                token,
                new_password: password,
            })
            setSuccess(true)
            setTimeout(() => {
                router.push('/login')
            }, 3000)
        } catch (err: unknown) {
            setError(getErrorMessage(err, t('common.error'), t))
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
                            {t('resetPassword.title')}
                        </h2>
                        <p className="text-gray-600">
                            {t('resetPassword.subtitle')}
                        </p>
                    </div>

                    {success ? (
                        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
                            <CheckCircle className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                            <div>
                                <p className="text-sm text-green-700 font-medium mb-1">
                                    {t('resetPassword.success')}
                                </p>
                                <p className="text-sm text-green-600">
                                    {t('resetPassword.redirecting')}
                                </p>
                            </div>
                        </div>
                    ) : (
                        <>
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
                                    <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                                        {t('changePassword.newPassword')}
                                    </label>
                                    <div className="relative">
                                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                            <Lock className="h-5 w-5 text-gray-400" />
                                        </div>
                                        <input
                                            id="password"
                                            name="password"
                                            type="password"
                                            required
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            className="input-field"
                                            style={{ paddingLeft: '2.75rem' }}
                                            placeholder={t('changePassword.newPasswordPlaceholder')}
                                        />
                                    </div>
                                </div>

                                <div>
                                    <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-2">
                                        {t('changePassword.confirmPassword')}
                                    </label>
                                    <div className="relative">
                                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                            <Lock className="h-5 w-5 text-gray-400" />
                                        </div>
                                        <input
                                            id="confirmPassword"
                                            name="confirmPassword"
                                            type="password"
                                            required
                                            value={confirmPassword}
                                            onChange={(e) => setConfirmPassword(e.target.value)}
                                            className="input-field"
                                            style={{ paddingLeft: '2.75rem' }}
                                            placeholder={t('changePassword.confirmPasswordPlaceholder')}
                                        />
                                    </div>
                                </div>

                                <p className="text-sm text-gray-600">
                                    {t('changePassword.requirements')}
                                </p>

                                <button
                                    type="submit"
                                    disabled={loading || !token}
                                    className="w-full btn-primary py-3 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {loading ? (
                                        <span className="flex items-center justify-center">
                                            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                            </svg>
                                            {t('resetPassword.resetting')}
                                        </span>
                                    ) : (
                                        t('resetPassword.resetPassword')
                                    )}
                                </button>
                            </form>
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
