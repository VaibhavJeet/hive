'use client'

import { useState, useEffect, useRef, ReactNode } from 'react'

type LogLevel = 'info' | 'warn' | 'error' | 'success' | 'debug' | 'system'

interface LogEntry {
  id: string | number
  timestamp: Date
  level: LogLevel
  message: string
  details?: string
}

interface TerminalProps {
  logs: LogEntry[]
  title?: string
  maxHeight?: string
  autoScroll?: boolean
  showTimestamp?: boolean
  showLevel?: boolean
  className?: string
  onClear?: () => void
  onCommand?: (command: string) => void
  showInput?: boolean
}

const levelConfig: Record<LogLevel, { color: string; prefix: string; bg: string }> = {
  info: {
    color: '#00f0ff',
    prefix: 'INFO',
    bg: 'rgba(0, 240, 255, 0.1)',
  },
  warn: {
    color: '#ffaa00',
    prefix: 'WARN',
    bg: 'rgba(255, 170, 0, 0.1)',
  },
  error: {
    color: '#ff0044',
    prefix: 'ERROR',
    bg: 'rgba(255, 0, 68, 0.1)',
  },
  success: {
    color: '#00ff88',
    prefix: 'OK',
    bg: 'rgba(0, 255, 136, 0.1)',
  },
  debug: {
    color: '#a0a0b0',
    prefix: 'DEBUG',
    bg: 'rgba(160, 160, 176, 0.1)',
  },
  system: {
    color: '#aa00ff',
    prefix: 'SYS',
    bg: 'rgba(170, 0, 255, 0.1)',
  },
}

export function Terminal({
  logs,
  title = 'System Terminal',
  maxHeight = '400px',
  autoScroll = true,
  showTimestamp = true,
  showLevel = true,
  className = '',
  onClear,
  onCommand,
  showInput = false,
}: TerminalProps) {
  const [command, setCommand] = useState('')
  const [commandHistory, setCommandHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  const handleCommand = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && command.trim()) {
      onCommand?.(command.trim())
      setCommandHistory([command.trim(), ...commandHistory])
      setCommand('')
      setHistoryIndex(-1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (historyIndex < commandHistory.length - 1) {
        const newIndex = historyIndex + 1
        setHistoryIndex(newIndex)
        setCommand(commandHistory[newIndex])
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1
        setHistoryIndex(newIndex)
        setCommand(commandHistory[newIndex])
      } else if (historyIndex === 0) {
        setHistoryIndex(-1)
        setCommand('')
      }
    }
  }

  return (
    <div
      className={`
        rounded-xl overflow-hidden
        bg-[#0a0a0f] border border-[#252538]
        font-mono text-sm
        ${className}
      `}
    >
      {/* Terminal header */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#12121a] border-b border-[#252538]">
        <div className="flex items-center gap-3">
          {/* Window controls */}
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-[#ff0044]" />
            <span className="w-3 h-3 rounded-full bg-[#ffaa00]" />
            <span className="w-3 h-3 rounded-full bg-[#00ff88]" />
          </div>

          <span className="text-[#00f0ff] text-xs uppercase tracking-wider">
            {title}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {onClear && (
            <button
              onClick={onClear}
              className="px-2 py-1 text-xs text-[#606080] hover:text-[#00f0ff] transition-colors"
            >
              CLEAR
            </button>
          )}
          <span className="text-[#00ff88] text-xs animate-pulse">LIVE</span>
        </div>
      </div>

      {/* Terminal content */}
      <div
        ref={scrollRef}
        className="overflow-auto p-4 space-y-1"
        style={{ maxHeight }}
        onClick={() => inputRef.current?.focus()}
      >
        {logs.length === 0 ? (
          <div className="text-[#606080] text-center py-8">
            <span className="neon-text-cyan">$</span> Waiting for output...
            <span className="terminal-cursor ml-1" />
          </div>
        ) : (
          logs.map((log) => {
            const config = levelConfig[log.level]
            return (
              <div
                key={log.id}
                className="flex items-start gap-2 py-0.5 hover:bg-white/[0.02] rounded px-1 -mx-1"
              >
                {/* Timestamp */}
                {showTimestamp && (
                  <span className="text-[#606080] text-xs flex-shrink-0">
                    [{formatTime(log.timestamp)}]
                  </span>
                )}

                {/* Level badge */}
                {showLevel && (
                  <span
                    className="text-xs px-1.5 py-0.5 rounded flex-shrink-0"
                    style={{
                      color: config.color,
                      backgroundColor: config.bg,
                    }}
                  >
                    {config.prefix}
                  </span>
                )}

                {/* Message */}
                <span style={{ color: config.color }}>
                  {log.message}
                  {log.details && (
                    <span className="text-[#606080] ml-2">{log.details}</span>
                  )}
                </span>
              </div>
            )
          })
        )}

        {/* Command input */}
        {showInput && (
          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-[#252538]">
            <span className="text-[#00ff88]">$</span>
            <input
              ref={inputRef}
              type="text"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              onKeyDown={handleCommand}
              className="flex-1 bg-transparent outline-none text-[#00ff88] caret-[#00ff88]"
              placeholder="Enter command..."
              spellCheck={false}
            />
            <span className="terminal-cursor" />
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-1.5 bg-[#12121a] border-t border-[#252538] text-[10px]">
        <span className="text-[#606080]">
          {logs.length} entries
        </span>
        <span className="text-[#606080]">
          SCROLL: {autoScroll ? 'AUTO' : 'MANUAL'}
        </span>
      </div>
    </div>
  )
}

// Helper function to create log entries
export function createLogEntry(
  level: LogLevel,
  message: string,
  details?: string
): LogEntry {
  return {
    id: Date.now() + Math.random(),
    timestamp: new Date(),
    level,
    message,
    details,
  }
}

// Compact log line component for inline use
interface LogLineProps {
  level: LogLevel
  message: string
  timestamp?: Date
  className?: string
}

export function LogLine({ level, message, timestamp, className = '' }: LogLineProps) {
  const config = levelConfig[level]

  return (
    <div className={`flex items-center gap-2 font-mono text-xs ${className}`}>
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: config.color }}
      />
      {timestamp && (
        <span className="text-[#606080]">
          {timestamp.toLocaleTimeString('en-US', { hour12: false })}
        </span>
      )}
      <span style={{ color: config.color }}>{message}</span>
    </div>
  )
}

// Activity feed component
interface ActivityFeedProps {
  activities: Array<{
    id: string | number
    type: LogLevel
    message: string
    time: Date
    icon?: ReactNode
  }>
  maxItems?: number
  className?: string
}

export function ActivityFeed({
  activities,
  maxItems = 10,
  className = '',
}: ActivityFeedProps) {
  const displayActivities = activities.slice(0, maxItems)

  return (
    <div className={`space-y-2 ${className}`}>
      {displayActivities.map((activity) => {
        const config = levelConfig[activity.type]
        return (
          <div
            key={activity.id}
            className="flex items-start gap-3 p-2 rounded-lg bg-[#1a1a2e]/50 hover:bg-[#1a1a2e]/80 transition-colors"
          >
            <div
              className="mt-1 p-1.5 rounded"
              style={{ backgroundColor: `${config.color}20` }}
            >
              {activity.icon || (
                <span
                  className="block w-2 h-2 rounded-full"
                  style={{ backgroundColor: config.color }}
                />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-[#e0e0e0] truncate">{activity.message}</p>
              <p className="text-xs text-[#606080] mt-0.5">
                {activity.time.toLocaleTimeString()}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
