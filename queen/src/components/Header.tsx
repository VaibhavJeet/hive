'use client'

import { useState, useEffect, useRef } from 'react'
import {
  Search,
  Bell,
  X,
  RefreshCw
} from 'lucide-react'
import { useConnectionStatus } from '@/contexts/WebSocketContext'

export function Header() {
  const [currentTime, setCurrentTime] = useState<string>('')
  const [searchFocused, setSearchFocused] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const notificationRef = useRef<HTMLDivElement>(null)
  const { statusText, statusColor, isConnected } = useConnectionStatus()

  useEffect(() => {
    const updateTime = () => {
      const now = new Date()
      setCurrentTime(now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }))
    }

    updateTime()
    const interval = setInterval(updateTime, 1000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setShowNotifications(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const notifications = [
    { id: 1, type: 'info', message: 'Bot activity engine started successfully', time: '2m ago', unread: true },
    { id: 2, type: 'info', message: '12 bots actively generating content', time: '5m ago', unread: true },
    { id: 3, type: 'warning', message: 'High engagement rate detected', time: '15m ago', unread: false },
  ]

  const unreadCount = notifications.filter(n => n.unread).length

  return (
    <header className="h-12 border-b border-[#2a2a2a] bg-[#0a0a0a]">
      <div className="h-full px-4 flex items-center justify-between gap-4">
        {/* Search bar */}
        <div className="flex-1 max-w-md">
          <div className="relative">
            <Search className={`
              absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5
              ${searchFocused ? 'text-[#e8e8e8]' : 'text-[#666666]'}
              transition-colors
            `} />
            <input
              type="text"
              placeholder="Search..."
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              className="
                w-full pl-9 pr-16 py-1.5
                bg-[#141414] border border-[#2a2a2a]
                rounded-md text-[12px] text-[#e8e8e8]
                placeholder-[#666666]
                focus:outline-none focus:border-[#3b82f6]
                transition-colors
              "
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
              <kbd className="px-1 py-0.5 text-[9px] text-[#666666] bg-[#1e1e1e] rounded border border-[#2a2a2a] font-mono">
                Ctrl+K
              </kbd>
            </div>
          </div>
        </div>

        {/* Right section */}
        <div className="flex items-center gap-2">
          {/* Real-time clock */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-md bg-[#141414] border border-[#2a2a2a]">
            <span className="text-[11px] font-mono text-[#888888] tabular-nums">
              {currentTime}
            </span>
            <div className="w-px h-3 bg-[#2a2a2a]" />
            <div className="flex items-center gap-1.5">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  backgroundColor: statusColor,
                  boxShadow: isConnected ? `0 0 4px ${statusColor}` : undefined
                }}
              />
              <span className="text-[10px] text-[#888888] uppercase">
                {statusText}
              </span>
            </div>
          </div>

          {/* Refresh button */}
          <button className="p-2 rounded-md bg-[#141414] border border-[#2a2a2a] hover:border-[#444444] text-[#888888] hover:text-[#e8e8e8] transition-colors">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          {/* Notification bell */}
          <div className="relative" ref={notificationRef}>
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="
                relative p-2 rounded-md
                bg-[#141414] border border-[#2a2a2a]
                hover:border-[#444444]
                transition-colors
              "
            >
              <Bell className="w-3.5 h-3.5 text-[#888888]" />
              {unreadCount > 0 && (
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-[#3b82f6] rounded-full flex items-center justify-center">
                  <span className="text-[9px] font-bold text-white">{unreadCount}</span>
                </div>
              )}
            </button>

            {/* Notifications dropdown */}
            {showNotifications && (
              <div className="
                absolute right-0 top-full mt-2 w-72
                bg-[#141414] border border-[#2a2a2a] rounded-lg
                shadow-xl z-50 overflow-hidden
              ">
                <div className="px-3 py-2 border-b border-[#2a2a2a] flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-[#e8e8e8] uppercase tracking-wider">
                    Notifications
                  </span>
                  <button
                    onClick={() => setShowNotifications(false)}
                    className="p-1 rounded hover:bg-[#1e1e1e] text-[#666666] hover:text-[#e8e8e8] transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {notifications.map((notif) => (
                    <div
                      key={notif.id}
                      className={`
                        px-3 py-2.5 border-b border-[#1e1e1e] hover:bg-[#1e1e1e] cursor-pointer transition-colors
                        ${notif.unread ? 'bg-[#1a1a2e]' : ''}
                      `}
                    >
                      <div className="flex items-start gap-2">
                        <div className={`
                          w-1.5 h-1.5 mt-1.5 rounded-full flex-shrink-0
                          ${notif.type === 'warning' ? 'bg-[#ffaa00]' : 'bg-[#3b82f6]'}
                        `} />
                        <div className="flex-1 min-w-0">
                          <p className="text-[11px] text-[#a0a0a0] leading-relaxed">{notif.message}</p>
                          <p className="text-[10px] text-[#666666] mt-1">{notif.time}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="px-3 py-2 bg-[#0a0a0a] border-t border-[#2a2a2a]">
                  <button className="w-full py-1 text-[10px] text-center text-[#3b82f6] hover:text-[#60a5fa] font-medium transition-colors">
                    View all
                  </button>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </header>
  )
}
