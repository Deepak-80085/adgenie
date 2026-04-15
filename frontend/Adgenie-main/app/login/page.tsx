'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
  const router = useRouter()
  const [tab, setTab] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const supabase = createClient()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setMessage(null)

    if (tab === 'signin') {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) {
        setError(error.message)
      } else {
        router.push('/')
        router.refresh()
      }
    } else {
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: { data: { full_name: fullName } },
      })
      if (error) {
        setError(error.message)
      } else {
        setMessage('Check your email to confirm your account, then sign in.')
        setTab('signin')
      }
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)] px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 text-center">
          <h1 className="font-serif text-3xl tracking-tight">AdGenie</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Create product ads in sixty seconds
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex border border-[var(--border)] mb-6">
          <button
            onClick={() => { setTab('signin'); setError(null) }}
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              tab === 'signin'
                ? 'bg-[var(--foreground)] text-[var(--background)]'
                : 'bg-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            Sign in
          </button>
          <button
            onClick={() => { setTab('signup'); setError(null) }}
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              tab === 'signup'
                ? 'bg-[var(--foreground)] text-[var(--background)]'
                : 'bg-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            Sign up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {tab === 'signup' && (
            <div>
              <label className="block text-xs font-medium mb-1 uppercase tracking-wide">
                Full name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Your name"
                className="w-full border border-[var(--border)] bg-transparent px-3 py-2 text-sm focus:outline-none focus:border-[var(--foreground)]"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium mb-1 uppercase tracking-wide">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="w-full border border-[var(--border)] bg-transparent px-3 py-2 text-sm focus:outline-none focus:border-[var(--foreground)]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1 uppercase tracking-wide">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={6}
              className="w-full border border-[var(--border)] bg-transparent px-3 py-2 text-sm focus:outline-none focus:border-[var(--foreground)]"
            />
          </div>

          {error && (
            <p className="text-xs text-red-600 border border-red-200 bg-red-50 px-3 py-2">
              {error}
            </p>
          )}
          {message && (
            <p className="text-xs text-green-700 border border-green-200 bg-green-50 px-3 py-2">
              {message}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[var(--foreground)] text-[var(--background)] py-2.5 text-sm font-medium hover:opacity-80 disabled:opacity-40 transition-opacity"
          >
            {loading ? 'Please wait…' : tab === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}
