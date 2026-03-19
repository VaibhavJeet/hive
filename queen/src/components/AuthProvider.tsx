'use client'

import { ReactNode } from 'react'

// No auth required - this is a public observation portal
export function AuthProvider({ children }: { children: ReactNode }) {
  return <>{children}</>
}
