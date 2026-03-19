'use client'


type StatusType = 'online' | 'offline' | 'warning' | 'error' | 'pending' | 'idle'
type StatusSize = 'sm' | 'md' | 'lg'

interface StatusIndicatorProps {
  status: StatusType
  label?: string
  size?: StatusSize
  pulse?: boolean
  showGlow?: boolean
  className?: string
}

const statusConfig: Record<StatusType, { color: string; glow: string; label: string }> = {
  online: {
    color: '#00ff88',
    glow: 'rgba(0, 255, 136, 0.5)',
    label: 'Online',
  },
  offline: {
    color: '#606080',
    glow: 'rgba(96, 96, 128, 0.3)',
    label: 'Offline',
  },
  warning: {
    color: '#ffaa00',
    glow: 'rgba(255, 170, 0, 0.5)',
    label: 'Warning',
  },
  error: {
    color: '#ff0044',
    glow: 'rgba(255, 0, 68, 0.5)',
    label: 'Error',
  },
  pending: {
    color: '#00f0ff',
    glow: 'rgba(0, 240, 255, 0.5)',
    label: 'Pending',
  },
  idle: {
    color: '#a0a0b0',
    glow: 'rgba(160, 160, 176, 0.3)',
    label: 'Idle',
  },
}

const sizeMap: Record<StatusSize, { dot: string; text: string; ring: string }> = {
  sm: { dot: 'w-2 h-2', text: 'text-xs', ring: 'w-4 h-4' },
  md: { dot: 'w-3 h-3', text: 'text-sm', ring: 'w-5 h-5' },
  lg: { dot: 'w-4 h-4', text: 'text-base', ring: 'w-6 h-6' },
}

export function StatusIndicator({
  status,
  label,
  size = 'md',
  pulse = true,
  showGlow = true,
  className = '',
}: StatusIndicatorProps) {
  const config = statusConfig[status]
  const sizeConfig = sizeMap[size]
  const shouldPulse = pulse && status !== 'offline' && status !== 'idle'

  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span className="relative flex items-center justify-center">
        {/* Pulse ring */}
        {shouldPulse && (
          <span
            className={`absolute ${sizeConfig.ring} rounded-full animate-ping`}
            style={{
              backgroundColor: config.color,
              opacity: 0.3,
            }}
          />
        )}

        {/* Main dot */}
        <span
          className={`relative ${sizeConfig.dot} rounded-full`}
          style={{
            backgroundColor: config.color,
            boxShadow: showGlow ? `0 0 10px ${config.glow}` : 'none',
          }}
        />
      </span>

      {/* Label */}
      {label !== undefined && (
        <span
          className={`font-mono ${sizeConfig.text}`}
          style={{ color: config.color }}
        >
          {label || config.label}
        </span>
      )}
    </span>
  )
}

// Status badge variant
interface StatusBadgeProps {
  status: StatusType
  label?: string
  size?: StatusSize
  className?: string
}

export function StatusBadge({
  status,
  label,
  size = 'md',
  className = '',
}: StatusBadgeProps) {
  const config = statusConfig[status]
  const sizeConfig = sizeMap[size]

  const paddingMap: Record<StatusSize, string> = {
    sm: 'px-2 py-0.5',
    md: 'px-3 py-1',
    lg: 'px-4 py-1.5',
  }

  return (
    <span
      className={`
        inline-flex items-center gap-2
        ${paddingMap[size]} rounded-full
        font-mono ${sizeConfig.text} uppercase tracking-wider
        border
        ${className}
      `}
      style={{
        color: config.color,
        backgroundColor: `${config.color}15`,
        borderColor: `${config.color}40`,
        boxShadow: `0 0 10px ${config.glow}`,
      }}
    >
      <span
        className={`${sizeConfig.dot} rounded-full`}
        style={{ backgroundColor: config.color }}
      />
      {label || config.label}
    </span>
  )
}

// Connection status component (like a server connection indicator)
interface ConnectionStatusProps {
  connected: boolean
  latency?: number
  serverName?: string
  className?: string
}

export function ConnectionStatus({
  connected,
  latency,
  serverName = 'Server',
  className = '',
}: ConnectionStatusProps) {
  const status = connected ? 'online' : 'offline'
  const config = statusConfig[status]

  const getLatencyColor = (ms: number) => {
    if (ms < 50) return '#00ff88'
    if (ms < 100) return '#00f0ff'
    if (ms < 200) return '#ffaa00'
    return '#ff0044'
  }

  return (
    <div
      className={`
        inline-flex items-center gap-3 px-4 py-2 rounded-lg
        bg-[#1a1a2e]/80 border border-[#252538]
        ${className}
      `}
    >
      <StatusIndicator status={status} size="sm" />

      <div className="flex flex-col">
        <span className="text-xs text-[#a0a0b0] font-mono uppercase">
          {serverName}
        </span>
        <span className="text-sm font-mono" style={{ color: config.color }}>
          {connected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {connected && latency !== undefined && (
        <div className="flex items-center gap-1 px-2 py-1 rounded bg-[#252538]">
          <span className="text-xs font-mono text-[#a0a0b0]">PING</span>
          <span
            className="text-xs font-mono font-bold"
            style={{ color: getLatencyColor(latency) }}
          >
            {latency}ms
          </span>
        </div>
      )}
    </div>
  )
}

// System status bar (multiple indicators in a row)
interface SystemStatusBarProps {
  items: Array<{
    label: string
    status: StatusType
    value?: string | number
  }>
  className?: string
}

export function SystemStatusBar({ items, className = '' }: SystemStatusBarProps) {
  return (
    <div
      className={`
        flex items-center gap-6 px-4 py-2 rounded-lg
        bg-[#12121a]/80 border border-[#252538]
        ${className}
      `}
    >
      {items.map((item, index) => (
        <div key={index} className="flex items-center gap-2">
          <StatusIndicator status={item.status} size="sm" />
          <div className="flex flex-col">
            <span className="text-[10px] text-[#606080] font-mono uppercase">
              {item.label}
            </span>
            {item.value !== undefined && (
              <span
                className="text-xs font-mono"
                style={{ color: statusConfig[item.status].color }}
              >
                {item.value}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
