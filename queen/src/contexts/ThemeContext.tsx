'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'

type Theme = 'dark' | 'light'

interface ThemeContextType {
  theme: Theme
  toggleTheme: () => void
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

/**
 * Theme Provider for dark/light mode support
 *
 * TODO: Issue #4 - Complete the dark/light mode toggle implementation
 *
 * Usage:
 * 1. Wrap your app with <ThemeProvider>
 * 2. Use the useTheme hook to access theme state and toggle function
 * 3. The provider manages the 'light' class on <html> element
 *
 * Example:
 * ```tsx
 * const { theme, toggleTheme } = useTheme()
 * return (
 *   <button onClick={toggleTheme}>
 *     {theme === 'dark' ? 'Switch to Light' : 'Switch to Dark'}
 *   </button>
 * )
 * ```
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('dark')
  const [mounted, setMounted] = useState(false)

  // Load saved theme on mount
  useEffect(() => {
    setMounted(true)
    const savedTheme = localStorage.getItem('hive-theme') as Theme | null
    if (savedTheme && (savedTheme === 'dark' || savedTheme === 'light')) {
      setThemeState(savedTheme)
      applyTheme(savedTheme)
    }
  }, [])

  const applyTheme = (newTheme: Theme) => {
    const root = document.documentElement
    if (newTheme === 'light') {
      root.classList.add('light')
    } else {
      root.classList.remove('light')
    }
  }

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
    localStorage.setItem('hive-theme', newTheme)
    applyTheme(newTheme)
  }

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark'
    setTheme(newTheme)
  }

  // Prevent hydration mismatch by not rendering until mounted
  if (!mounted) {
    return <>{children}</>
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
