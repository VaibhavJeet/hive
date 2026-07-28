'use client'

import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { AuthError, login } from '@/lib/auth'

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const next = searchParams.get('next') || '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      await login(email, password)
      router.replace(next)
    } catch (err) {
      // Do not distinguish "no such user" from "wrong password" — that difference
      // is a user-enumeration oracle.
      setError(
        err instanceof AuthError && err.status === 401
          ? 'Invalid email or password.'
          : err instanceof Error
            ? err.message
            : 'Sign in failed.'
      )
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-mono uppercase tracking-[0.2em] text-[#e0e0e0]">
            Hive
          </h1>
          <p className="mt-2 text-xs font-mono uppercase tracking-wider text-[#606080]">
            Observation Portal
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-lg border border-[#252538] bg-[#12121a] p-6"
        >
          <label
            htmlFor="email"
            className="block text-xs font-mono uppercase tracking-wider text-[#606080]"
          >
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-2 w-full rounded-lg border border-[#252538] bg-[#0a0a0a] px-3 py-2
              font-mono text-sm text-[#e0e0e0] placeholder-[#606080]
              focus:border-[#00f0ff] focus:outline-none"
          />

          <label
            htmlFor="password"
            className="mt-5 block text-xs font-mono uppercase tracking-wider text-[#606080]"
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-2 w-full rounded-lg border border-[#252538] bg-[#0a0a0a] px-3 py-2
              font-mono text-sm text-[#e0e0e0] placeholder-[#606080]
              focus:border-[#00f0ff] focus:outline-none"
          />

          {error && (
            <p
              role="alert"
              className="mt-4 rounded border border-[#ff4444]/40 bg-[#ff4444]/10 px-3 py-2
                font-mono text-xs text-[#ff8888]"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-6 w-full rounded-lg border border-[#00f0ff]/40 bg-[#00f0ff]/10 px-4 py-2
              font-mono text-sm uppercase tracking-wider text-[#00f0ff]
              transition-colors hover:bg-[#00f0ff]/20 disabled:opacity-40"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-6 text-center font-mono text-xs text-[#606080]">
          Civilization pages are public. Sign in is required for admin views.
        </p>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#0a0a0a]" />}>
      <LoginForm />
    </Suspense>
  )
}
