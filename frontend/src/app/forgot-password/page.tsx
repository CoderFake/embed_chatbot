'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { apiClient } from '@/lib/auth-api'
import { getErrorMessage } from '@/lib/error-utils'
import { Logo } from '@/components/Logo'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { useLanguage } from '@/contexts/language-context'
import { Mail, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react'

export default function ForgotPasswordPage() {
    const router = useRouter()
    const { t } = useLanguage()
    const [email, setEmail] = useState('')
    const [error, setError] = useState('')
    const [success, setSuccess] = useState(false)
    const [loading, setLoading] = useState(false)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setLoading(true)

        const normalizedEmail = email.trim().toLowerCase()

        try {
            await apiClient.post('/auth/forgot-password', { email: normalizedEmail })
            setSuccess(true)
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
                            {t('forgotPassword.title')}
                        </h2>
                        <p className="text-gray-600">
                            {t('forgotPassword.subtitle')}
                        </p>
                    </div>

                    {success ? (
                        <>
                            {/* Success Message */}
                            <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
                                <CheckCircle className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                                <div>
                                    <p className="text-sm text-green-700 font-medium mb-1">
                                        {t('forgotPassword.emailSent')}
                                    </p>
                                    <p className="text-sm text-green-600">
                                        {t('forgotPassword.checkYourEmail')}
                                    </p>
                                </div>
                            </div>

                            <button
                                onClick={() => router.push('/login')}
                                className="w-full btn-secondary py-3 flex items-center justify-center gap-2"
                            >
                                <ArrowLeft className="w-5 h-5" />
                                {t('forgotPassword.backToLogin')}
                            </button>
                        </>
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
                                            {t('forgotPassword.sending')}
                                        </span>
                                    ) : (
                                        t('forgotPassword.sendResetLink')
                                    )}
                                </button>
                            </form>

                            {/* Back to Login */}
                            <div className="mt-6 text-center">
                                <Link
                                    href="/login"
                                    className="text-sm text-gray-600 hover:text-gray-900 flex items-center justify-center gap-1"
                                >
                                    <ArrowLeft className="w-4 h-4" />
                                    {t('forgotPassword.backToLogin')}
                                </Link>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
