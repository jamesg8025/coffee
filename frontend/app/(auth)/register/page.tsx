'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { CheckCircle, Circle } from 'lucide-react'

const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_URL ?? 'http://localhost:8001'

const passwordSchema = z
  .string()
  .min(8, 'At least 8 characters')
  .regex(/[A-Z]/, 'At least one uppercase letter')
  .regex(/[a-z]/, 'At least one lowercase letter')
  .regex(/[0-9]/, 'At least one digit')
  .regex(/[^A-Za-z0-9]/, 'At least one special character')

const registerSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: passwordSchema,
})

type RegisterFormValues = z.infer<typeof registerSchema>

interface PasswordRequirement {
  label: string
  test: (val: string) => boolean
}

const requirements: PasswordRequirement[] = [
  { label: '8+ characters', test: (v) => v.length >= 8 },
  { label: 'Uppercase letter', test: (v) => /[A-Z]/.test(v) },
  { label: 'Lowercase letter', test: (v) => /[a-z]/.test(v) },
  { label: 'Digit', test: (v) => /[0-9]/.test(v) },
  { label: 'Special character', test: (v) => /[^A-Za-z0-9]/.test(v) },
]

interface ApiValidationError {
  detail?: string | { msg: string; loc?: string[] }[]
}

export default function RegisterPage() {
  const router = useRouter()
  const [serverError, setServerError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  })

  const passwordValue = watch('password', '')

  async function onSubmit(values: RegisterFormValues) {
    setServerError(null)
    setIsSubmitting(true)
    try {
      const res = await fetch(`${AUTH_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: values.email, password: values.password }),
      })

      if (res.ok) {
        router.push('/login?registered=1')
        return
      }

      const data: ApiValidationError = await res.json()
      if (typeof data.detail === 'string') {
        setServerError(data.detail)
      } else if (Array.isArray(data.detail) && data.detail.length > 0) {
        setServerError(data.detail.map((e) => e.msg).join(', '))
      } else {
        setServerError('Registration failed. Please try again.')
      }
    } catch {
      setServerError('Network error. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-56px)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-stone-900">Create account</h1>
            <p className="text-stone-500 text-sm mt-1">
              Join the Coffee Connoisseur community
            </p>
          </div>

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
                autoComplete="new-password"
                className={`w-full px-3 py-2 rounded-lg border text-stone-900 text-sm placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition ${
                  errors.password
                    ? 'border-red-400 bg-red-50'
                    : 'border-stone-300 bg-white'
                }`}
                placeholder="••••••••"
              />

              <ul className="mt-2 space-y-1">
                {requirements.map((req) => {
                  const met = req.test(passwordValue)
                  return (
                    <li key={req.label} className="flex items-center gap-1.5 text-xs">
                      {met ? (
                        <CheckCircle className="w-3.5 h-3.5 text-green-500 shrink-0" />
                      ) : (
                        <Circle className="w-3.5 h-3.5 text-stone-300 shrink-0" />
                      )}
                      <span className={met ? 'text-green-700' : 'text-stone-400'}>
                        {req.label}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-amber-950 hover:bg-amber-900 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors text-sm mt-2"
            >
              {isSubmitting ? 'Creating account…' : 'Create account'}
            </button>
          </form>

          <p className="text-center text-stone-500 text-sm mt-6">
            Already have an account?{' '}
            <Link href="/login" className="text-amber-800 hover:text-amber-600 font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
