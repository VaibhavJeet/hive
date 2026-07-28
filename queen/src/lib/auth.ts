/**
 * Session auth for the queen portal.
 *
 * Replaces the hardcoded `ADMIN_USER_ID` + `X-User-ID` header scheme (HIVE-002) with
 * JWT bearer tokens issued by the backend's `/auth/*` endpoints (HIVE-001).
 *
 * Storage note: tokens live in `localStorage`, which is readable by any script on the
 * origin. That is acceptable only because the portal has a strict CSP and no third-party
 * scripts. If that changes, move the refresh token to an httpOnly cookie — see HIVE-068.
 */

import { API_BASE_URL } from './api'

const ACCESS_TOKEN_KEY = 'hive.access_token'
const REFRESH_TOKEN_KEY = 'hive.refresh_token'
const USER_KEY = 'hive.user'

export interface SessionUser {
  id: string
  email: string
  display_name: string
  avatar_seed: string
  created_at: string
}

interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: SessionUser
}

interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

// ============================================================================
// STORAGE
// ============================================================================

const isBrowser = () => typeof window !== 'undefined'

export function getAccessToken(): string | null {
  return isBrowser() ? localStorage.getItem(ACCESS_TOKEN_KEY) : null
}

export function getRefreshToken(): string | null {
  return isBrowser() ? localStorage.getItem(REFRESH_TOKEN_KEY) : null
}

export function getSessionUser(): SessionUser | null {
  if (!isBrowser()) return null
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as SessionUser
  } catch {
    return null
  }
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null
}

function storeSession(tokens: TokenPair, user?: SessionUser): void {
  if (!isBrowser()) return
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
  notifyAuthChange()
}

export function clearSession(): void {
  if (!isBrowser()) return
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  // Sweep the retired pre-HIVE-002 key so old browsers stop presenting it.
  localStorage.removeItem('admin_user_id')
  notifyAuthChange()
}

// ============================================================================
// CHANGE NOTIFICATION
// ============================================================================

type AuthListener = () => void
const listeners = new Set<AuthListener>()

export function onAuthChange(listener: AuthListener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/**
 * Snapshot for `useSyncExternalStore`. Must be referentially stable between changes,
 * so it is a cached string rather than an object.
 */
const SERVER_SNAPSHOT = 'server'
let cachedSnapshot: string | null = null

function computeSnapshot(): string {
  if (!isBrowser()) return SERVER_SNAPSHOT
  const signedIn = localStorage.getItem(ACCESS_TOKEN_KEY) ? '1' : '0'
  return `${signedIn}|${localStorage.getItem(USER_KEY) ?? ''}`
}

export function getAuthSnapshot(): string {
  if (cachedSnapshot === null) cachedSnapshot = computeSnapshot()
  return cachedSnapshot
}

/** During SSR and hydration there is no localStorage — callers treat this as "unknown". */
export function getServerAuthSnapshot(): string {
  return SERVER_SNAPSHOT
}

export function isSnapshotHydrated(snapshot: string): boolean {
  return snapshot !== SERVER_SNAPSHOT
}

export function isSnapshotSignedIn(snapshot: string): boolean {
  return snapshot.startsWith('1|')
}

/** The snapshot carries the serialized user, so readers never re-touch localStorage. */
export function parseSnapshotUser(snapshot: string): SessionUser | null {
  if (!isSnapshotHydrated(snapshot)) return null
  const raw = snapshot.slice(snapshot.indexOf('|') + 1)
  if (!raw) return null
  try {
    return JSON.parse(raw) as SessionUser
  } catch {
    return null
  }
}

function notifyAuthChange(): void {
  cachedSnapshot = computeSnapshot()
  listeners.forEach((l) => {
    try {
      l()
    } catch {
      // A listener must never break the auth flow.
    }
  })
}

// Keep tabs in sync: signing out in one tab must sign out the others.
if (isBrowser()) {
  window.addEventListener('storage', (event) => {
    if (
      event.key === null ||
      event.key === ACCESS_TOKEN_KEY ||
      event.key === USER_KEY
    ) {
      notifyAuthChange()
    }
  })
}

// ============================================================================
// AUTH OPERATIONS
// ============================================================================

export class AuthError extends Error {
  constructor(message: string, public status: number) {
    super(message)
    this.name = 'AuthError'
  }
}

async function postJson<T>(endpoint: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      detail = (await response.json())?.detail ?? detail
    } catch {
      // Non-JSON error body — keep the status text.
    }
    throw new AuthError(detail, response.status)
  }

  return response.json()
}

export async function login(email: string, password: string): Promise<SessionUser> {
  const auth = await postJson<AuthResponse>('/auth/login', { email, password })
  storeSession(auth, auth.user)
  return auth.user
}

export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken()
  clearSession()
  if (!refreshToken) return
  try {
    await postJson('/auth/logout', { refresh_token: refreshToken })
  } catch {
    // The local session is already gone; a failed server-side revoke must not
    // leave the user stuck in a logged-in-looking state.
  }
}

/**
 * Exchange the refresh token for a new access token.
 *
 * Concurrent 401s must not each fire their own refresh, so in-flight refreshes are
 * shared. Returns the new access token, or null if the session is unrecoverable.
 */
let inFlightRefresh: Promise<string | null> | null = null

export function refreshAccessToken(): Promise<string | null> {
  if (inFlightRefresh) return inFlightRefresh

  inFlightRefresh = (async () => {
    const refreshToken = getRefreshToken()
    if (!refreshToken) return null

    try {
      const tokens = await postJson<TokenPair>('/auth/refresh', {
        refresh_token: refreshToken,
      })
      storeSession(tokens)
      return tokens.access_token
    } catch {
      clearSession()
      return null
    } finally {
      inFlightRefresh = null
    }
  })()

  return inFlightRefresh
}

/** Send the user to the login page, preserving where they were headed. */
export function redirectToLogin(): void {
  if (!isBrowser()) return
  const next = encodeURIComponent(window.location.pathname + window.location.search)
  if (window.location.pathname !== '/login') {
    window.location.href = `/login?next=${next}`
  }
}
