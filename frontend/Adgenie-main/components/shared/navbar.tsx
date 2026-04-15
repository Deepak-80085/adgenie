'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { APP_NAME } from '@/lib/mock-data'
import { createClient } from '@/lib/supabase/client'
import type { User } from '@supabase/supabase-js'

type NavbarProps = {
  showCreate?: boolean
}

export function Navbar({ showCreate = true }: NavbarProps) {
  const router = useRouter()
  const supabase = createClient()
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user))

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })
    return () => subscription.unsubscribe()
  }, [])

  async function handleSignOut() {
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  const initials = user?.user_metadata?.full_name
    ? user.user_metadata.full_name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.email?.slice(0, 2).toUpperCase() ?? '??'

  return (
    <header className="sticky top-0 z-30 w-full border-b border-[var(--border)] bg-[var(--background)]">
      <div className="mx-auto flex min-h-16 w-full max-w-[1200px] items-center justify-between gap-3 px-3 py-2 sm:px-5 md:min-h-18 md:px-8">
        <Link href="/" className="font-[var(--font-instrument-serif)] text-[20px] tracking-tight">
          {APP_NAME}
        </Link>

        <div className="flex items-center gap-2 sm:gap-3 md:gap-6">
          {showCreate && (
            <Button
              asChild
              size="sm"
              variant="default"
              className="hidden border border-black bg-black font-medium text-white hover:bg-black/90 sm:inline-flex"
            >
              <Link href="/create">Create ad</Link>
            </Button>
          )}
          {showCreate && (
            <Button asChild size="sm" variant="secondary" className="border-[var(--foreground)] px-2 sm:px-3">
              <Link href="/dashboard">Library</Link>
            </Button>
          )}

          {user ? (
            <div className="flex items-center gap-2">
              <span
                className="grid h-8 min-w-8 place-items-center rounded-full border border-[var(--border)] bg-[var(--card)] px-2 text-xs font-semibold sm:h-9 sm:min-w-9"
                title={user.email}
              >
                {initials}
              </span>
              <button
                onClick={handleSignOut}
                className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
              >
                Sign out
              </button>
            </div>
          ) : (
            <Button asChild size="sm" variant="secondary" className="border-[var(--foreground)] px-2 sm:px-3">
              <Link href="/login">Sign in</Link>
            </Button>
          )}
        </div>
      </div>
    </header>
  )
}
