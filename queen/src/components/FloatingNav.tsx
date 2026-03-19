'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Globe2,
  Bot,
  Users,
  Sparkles,
  ScrollText,
  Clock,
  Activity,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
} from 'lucide-react'
import { useConnectionStatus } from '@/contexts/WebSocketContext'

const navItems = [
  { name: 'CIVILIZATION', href: '/', icon: Globe2, hot: true },
  { name: 'BOTS', href: '/bots', icon: Bot },
  { name: 'CIRCLES', href: '/circles', icon: Users },
  { name: 'CULTURE', href: '/culture', icon: Sparkles },
  { name: 'TIMELINE', href: '/timeline', icon: Clock },
  { name: 'RITUALS', href: '/rituals', icon: ScrollText },
]

const systemItems = [
  { name: 'HEALTH', href: '/system', icon: Activity },
  { name: 'SETTINGS', href: '/settings', icon: Settings },
]

export function FloatingNav() {
  const pathname = usePathname()
  const [expanded, setExpanded] = useState(false)
  const { statusColor, statusText, isConnected } = useConnectionStatus()

  return (
    <>
      {/* Floating sidebar */}
      <nav
        className={`
          fixed left-4 top-1/2 -translate-y-1/2 z-50
          flex flex-col gap-1 p-2
          bg-[#0d0d0d]/95 backdrop-blur-xl
          border border-[#1a1a1a] rounded-xl
          shadow-[0_0_40px_rgba(0,0,0,0.5)]
          transition-all duration-200
          ${expanded ? 'w-44' : 'w-12'}
        `}
        onMouseEnter={() => setExpanded(true)}
        onMouseLeave={() => setExpanded(false)}
      >
        {/* Logo */}
        <div className={`flex items-center gap-2 px-2 py-2 mb-2 ${expanded ? '' : 'justify-center'}`}>
          <div className="w-7 h-7 rounded-lg bg-[#44ff88]/10 border border-[#44ff88]/30 flex items-center justify-center">
            <Zap className="w-4 h-4 text-[#44ff88]" />
          </div>
          {expanded && (
            <span className="text-[10px] font-bold text-[#44ff88] tracking-wider">SENTIENT</span>
          )}
        </div>

        {/* Divider */}
        <div className="h-px bg-[#1a1a1a] mx-1 mb-1" />

        {/* Main nav items */}
        {navItems.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`
                relative flex items-center gap-3 px-2.5 py-2 rounded-lg
                transition-all duration-150 group
                ${isActive
                  ? 'bg-[#44ff88]/10 text-[#44ff88]'
                  : 'text-[#666666] hover:text-[#e8e8e8] hover:bg-[#1a1a1a]'
                }
                ${expanded ? '' : 'justify-center'}
              `}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {expanded && (
                <span className="text-[10px] font-medium tracking-wider">{item.name}</span>
              )}
              {item.hot && !expanded && (
                <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-[#ff4444] rounded-full" />
              )}
              {item.hot && expanded && (
                <span className="ml-auto px-1.5 py-0.5 text-[8px] bg-[#ff4444] text-white rounded font-bold">
                  LIVE
                </span>
              )}
            </Link>
          )
        })}

        {/* Divider */}
        <div className="h-px bg-[#1a1a1a] mx-1 my-1" />

        {/* System items */}
        {systemItems.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`
                flex items-center gap-3 px-2.5 py-2 rounded-lg
                transition-all duration-150
                ${isActive
                  ? 'bg-[#1a1a1a] text-[#e8e8e8]'
                  : 'text-[#555555] hover:text-[#888888] hover:bg-[#141414]'
                }
                ${expanded ? '' : 'justify-center'}
              `}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {expanded && (
                <span className="text-[10px] font-medium tracking-wider">{item.name}</span>
              )}
            </Link>
          )
        })}

        {/* Connection status */}
        <div className="h-px bg-[#1a1a1a] mx-1 my-1" />
        <div className={`flex items-center gap-2 px-2.5 py-2 ${expanded ? '' : 'justify-center'}`}>
          <div
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{
              backgroundColor: statusColor,
              boxShadow: isConnected ? `0 0 8px ${statusColor}` : undefined
            }}
          />
          {expanded && (
            <span className="text-[9px] text-[#555555] uppercase tracking-wider">{statusText}</span>
          )}
        </div>
      </nav>

      {/* Top bar with time and controls */}
      <header className="fixed top-4 left-1/2 -translate-x-1/2 z-40">
        <div className="flex items-center gap-3 px-4 py-2 bg-[#0d0d0d]/90 backdrop-blur-xl border border-[#1a1a1a] rounded-full">
          <span className="text-[11px] font-mono text-[#44ff88]">
            {new Date().toLocaleTimeString('en-US', { hour12: false })}
          </span>
          <div className="w-px h-3 bg-[#2a2a2a]" />
          <span className="text-[10px] text-[#666666] uppercase tracking-wider">
            OBSERVATION PORTAL
          </span>
        </div>
      </header>

      {/* Right controls (like world-monitor) */}
      <div className="fixed right-4 top-1/2 -translate-y-1/2 z-40 flex flex-col gap-2">
        <button className="p-2.5 bg-[#0d0d0d]/90 backdrop-blur-xl border border-[#1a1a1a] rounded-lg text-[#666666] hover:text-[#e8e8e8] transition-colors">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <button className="p-2.5 bg-[#0d0d0d]/90 backdrop-blur-xl border border-[#1a1a1a] rounded-lg text-[#666666] hover:text-[#e8e8e8] transition-colors">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </>
  )
}
