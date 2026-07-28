'use client'

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
} from 'react'
import { usePathname, useRouter } from 'next/navigation'
import {
  SessionUser,
  getAuthSnapshot,
  getServerAuthSnapshot,
  isSnapshotHydrated,
  isSnapshotSignedIn,
  parseSnapshotUser,
  logout as logoutSession,
  onAuthChange,
} from '@/lib/auth'

/**
 * Civilization observation is public by design (VISION.md: "Observation over control").
 * Admin surfaces are not — these routes require a session.
 */
const PROTECTED_PREFIXES = [
  '/analytics',
  '/bots',
  '/logs',
  '/posts',
  '/reports',
  '/settings',
  '/system',
]

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  )
}

interface AuthContextValue {
  user: SessionUser | null
  isSignedIn: boolean
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()

  // Auth lives in localStorage — an external store. Subscribing via
  // useSyncExternalStore (rather than an effect that calls setState) keeps SSR,
  // hydration, and cross-tab updates correct without cascading renders.
  const snapshot = useSyncExternalStore(
    onAuthChange,
    getAuthSnapshot,
    getServerAuthSnapshot
  )

  // `server` until hydration completes, so nothing is gated on a guessed answer.
  const hydrated = isSnapshotHydrated(snapshot)
  const signedIn = isSnapshotSignedIn(snapshot)
  const user = useMemo<SessionUser | null>(
    () => parseSnapshotUser(snapshot),
    [snapshot]
  )

  useEffect(() => {
    if (!hydrated) return
    if (isProtected(pathname) && !signedIn) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`)
    }
  }, [hydrated, pathname, signedIn, router])

  const logout = useCallback(async () => {
    await logoutSession()
    router.replace('/login')
  }, [router])

  // Hold the paint on protected routes until we know whether there is a session,
  // so admin data never flashes before the redirect lands.
  const gated = hydrated && isProtected(pathname) && !signedIn

  return (
    <AuthContext.Provider value={{ user, isSignedIn: signedIn, logout }}>
      {gated ? <div className="min-h-screen bg-[#0a0a0a]" /> : children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
