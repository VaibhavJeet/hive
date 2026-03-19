'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import {
  LayoutDashboard,
  BarChart3,
  Bot,
  Users,
  Building2,
  FileText,
  Activity,
  Settings,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Cpu,
  Zap,
  Globe2
} from 'lucide-react'
import { useConnectionStatus } from '@/contexts/WebSocketContext'

const navigation = [
  {
    section: 'Overview',
    items: [
      { name: 'Dashboard', href: '/', icon: LayoutDashboard },
      { name: 'Analytics', href: '/analytics', icon: BarChart3 },
      { name: 'Civilization', href: '/civilization', icon: Globe2 },
    ]
  },
  {
    section: 'Social',
    items: [
      { name: 'Bots', href: '/bots', icon: Bot },
      { name: 'Circles', href: '/circles', icon: Building2 },
    ]
  },
  {
    section: 'Content',
    items: [
      { name: 'Posts', href: '/posts', icon: FileText },
      { name: 'Reports', href: '/reports', icon: AlertTriangle },
    ]
  },
  {
    section: 'System',
    items: [
      { name: 'Health', href: '/system', icon: Activity },
      { name: 'Logs', href: '/logs', icon: Cpu },
      { name: 'Settings', href: '/settings', icon: Settings },
    ]
  },
]

export function Sidebar() {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)
  const { statusColor, statusText, isConnected } = useConnectionStatus()

  return (
    <>
      {/* Mobile overlay */}
      <div
        className={`fixed inset-0 bg-black/60 z-40 lg:hidden ${
          collapsed ? 'hidden' : 'block'
        }`}
        onClick={() => setCollapsed(true)}
      />

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:relative z-50 h-screen
          ${collapsed ? 'w-[60px]' : 'w-[240px]'}
          transition-all duration-200 ease-out
          bg-[#0a0a0a]
          border-r border-[#2a2a2a]
          flex flex-col
        `}
      >
        {/* Logo area */}
        <div className={`p-4 ${collapsed ? 'px-3' : ''}`}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-[#141414] border border-[#2a2a2a] flex items-center justify-center">
              <Zap className="w-4 h-4 text-[#44ff88]" />
            </div>
            {!collapsed && (
              <div className="flex flex-col">
                <span className="text-[13px] font-semibold text-[#e8e8e8] tracking-tight">
                  SENTIENT
                </span>
                <span className="text-[9px] text-[#666666] tracking-wider uppercase">
                  Command Center
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Connection status */}
        <div className={`mx-3 mb-3 ${collapsed ? 'mx-2' : ''}`}>
          <div
            className={`
              flex items-center gap-2 px-3 py-1.5 rounded-md
              bg-[#141414] border border-[#2a2a2a]
              ${collapsed ? 'justify-center px-2' : ''}
            `}
          >
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{
                backgroundColor: statusColor,
                boxShadow: isConnected ? `0 0 6px ${statusColor}` : undefined
              }}
            />
            {!collapsed && (
              <span className="text-[10px] text-[#888888] uppercase tracking-wider">
                {statusText}
              </span>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 overflow-y-auto">
          {navigation.map((section) => (
            <div key={section.section} className="mb-4">
              {!collapsed && (
                <h3 className="px-3 mb-1 text-[9px] font-medium text-[#555555] uppercase tracking-wider">
                  {section.section}
                </h3>
              )}
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const isActive = pathname === item.href
                  const Icon = item.icon

                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={`
                        group relative flex items-center gap-3 px-3 py-2 rounded-md
                        transition-all duration-150
                        ${isActive
                          ? 'bg-[#1e1e1e] text-[#e8e8e8]'
                          : 'text-[#888888] hover:text-[#e8e8e8] hover:bg-[#141414]'
                        }
                        ${collapsed ? 'justify-center px-2' : ''}
                      `}
                    >
                      {/* Active indicator */}
                      {isActive && (
                        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-[#44ff88] rounded-r" />
                      )}

                      <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-[#44ff88]' : ''}`} />

                      {!collapsed && (
                        <span className="text-[12px] font-medium">
                          {item.name}
                        </span>
                      )}

                      {/* Tooltip for collapsed state */}
                      {collapsed && (
                        <div className="
                          absolute left-full ml-2 px-2 py-1
                          bg-[#141414] text-[#e8e8e8] text-[11px] rounded
                          opacity-0 group-hover:opacity-100
                          pointer-events-none transition-opacity
                          whitespace-nowrap z-50
                          border border-[#2a2a2a]
                        ">
                          {item.name}
                        </div>
                      )}
                    </Link>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="
            absolute -right-3 top-16
            w-6 h-6 rounded-full
            bg-[#141414] border border-[#2a2a2a]
            flex items-center justify-center
            text-[#666666] hover:text-[#e8e8e8]
            hover:border-[#444444]
            transition-all duration-150
            hidden lg:flex
          "
        >
          {collapsed ? (
            <ChevronRight className="w-3 h-3" />
          ) : (
            <ChevronLeft className="w-3 h-3" />
          )}
        </button>
      </aside>
    </>
  )
}
