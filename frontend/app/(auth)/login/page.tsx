'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/contexts/auth'

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

type LoginFormValues = z.infer<typeof loginSchema>

export default function LoginPage() {
  const { login } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const registered = searchParams.get('registered')

  const [serverError, setServerError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  async function onSubmit(values: LoginFormValues) {
    setServerError(null)
    setIsSubmitting(true)
    try {
      const result = await login(values.email, values.password)

      if ('error' in result) {
        setServerError(result.error)
        return
      }

      if ('mfaRequired' in result && result.mfaRequired) {
        router.push(`/mfa?token=${encodeURIComponent(result.mfaToken)}`)
        return
      }

      router.replace('/catalog')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-56px)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-stone-900">Welcome back</h1>
            <p className="text-stone-500 text-sm mt-1">
              Sign in to your Coffee Connoisseur account
            </p>
          </div>

          {registered && (
            <div className="mb-4 bg-green-50 border border-green-200 text-green-800 text-sm rounded-lg px-4 py-3">
              Account created successfully. Please sign in.
            </div>
          )}

          {serverError && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg px-4 py-3">
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-stone-700 mb-1"
              >
                Email
              </label>
              <input
                {...register('email')}
                id="email"
                type="email"
                autoComplete="email"
                className={`w-full px-3 py-2 rounded-lg border text-stone-900 text-sm placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition ${
                  errors.email
                    ? 'border-red-400 bg-red-50'
                    : 'border-stone-300 bg-white'
                }`}
                placeholder="you@example.com"
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-stone-700 mb-1"
              >
                Password
              </label>
              <input
                {...register('password')}
                id="password"
                type="password"
                autoComplete="current-password"
                className={`w-full px-3 py-2 rounded-lg border text-stone-900 text-sm placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition ${
                  errors.password
                    ? 'border-red-400 bg-red-50'
                    : 'border-stone-300 bg-white'
                }`}
                placeholder="••••••••"
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">
                  {errors.password.message}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-amber-950 hover:bg-amber-900 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors text-sm mt-2"
            >
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="text-center text-stone-500 text-sm mt-6">
            Don&apos;t have an account?{' '}
            <Link href="/register" className="text-amber-800 hover:text-amber-600 font-medium">
              Register
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
