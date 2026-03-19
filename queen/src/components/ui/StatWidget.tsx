'use client'

import { ReactNode, useEffect, useState } from 'react'
import { LucideIcon } from 'lucide-react'

type WidgetColor = 'cyan' | 'magenta' | 'green' | 'amber' | 'purple'

interface StatWidgetProps {
  title: string
  value: number | string
  icon?: LucideIcon
  suffix?: string
  prefix?: string
  trend?: {
    value: number
    isPositive: boolean
  }
  sparkline?: number[]
  color?: WidgetColor
  loading?: boolean
  animate?: boolean
  compact?: boolean
  className?: string
}

const colorMap: Record<WidgetColor, { primary: string; glow: string; bg: string }> = {
  cyan: {
    primary: '#00f0ff',
    glow: 'rgba(0, 240, 255, 0.5)',
    bg: 'rgba(0, 240, 255, 0.1)',
  },
  magenta: {
    primary: '#ff00aa',
    glow: 'rgba(255, 0, 170, 0.5)',
    bg: 'rgba(255, 0, 170, 0.1)',
  },
  green: {
    primary: '#00ff88',
    glow: 'rgba(0, 255, 136, 0.5)',
    bg: 'rgba(0, 255, 136, 0.1)',
  },
  amber: {
    primary: '#ffaa00',
    glow: 'rgba(255, 170, 0, 0.5)',
    bg: 'rgba(255, 170, 0, 0.1)',
  },
  purple: {
    primary: '#aa00ff',
    glow: 'rgba(170, 0, 255, 0.5)',
    bg: 'rgba(170, 0, 255, 0.1)',
  },
}

// Animated number component
function AnimatedNumber({ value, duration = 1000 }: { value: number; duration?: number }) {
  const [displayValue, setDisplayValue] = useState(0)

  useEffect(() => {
    const startTime = Date.now()
    const startValue = displayValue
    const diff = value - startValue

    const animate = () => {
      const elapsed = Date.now() - startTime
      const progress = Math.min(elapsed / duration, 1)
      const easeOut = 1 - Math.pow(1 - progress, 3)
      setDisplayValue(Math.round(startValue + diff * easeOut))

      if (progress < 1) {
        requestAnimationFrame(animate)
      }
    }

    requestAnimationFrame(animate)
  }, [value, duration, displayValue])

  return <span>{displayValue.toLocaleString()}</span>
}

// Mini sparkline component
function Sparkline({ data, color, height = 30 }: { data: number[]; color: string; height?: number }) {
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const width = 100

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((val - min) / range) * height
    return `${x},${y}`
  }).join(' ')

  return (
    <svg className="w-full" style={{ height }} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <linearGradient id={`sparkline-gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.5" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Fill area */}
      <polygon
        points={`0,${height} ${points} ${width},${height}`}
        fill={`url(#sparkline-gradient-${color})`}
      />
      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ filter: `drop-shadow(0 0 4px ${color})` }}
      />
      {/* Current value dot */}
      <circle
        cx={width}
        cy={height - ((data[data.length - 1] - min) / range) * height}
        r="3"
        fill={color}
        style={{ filter: `drop-shadow(0 0 6px ${color})` }}
      />
    </svg>
  )
}

export function StatWidget({
  title,
  value,
  icon: Icon,
  suffix = '',
  prefix = '',
  trend,
  sparkline,
  color = 'cyan',
  loading = false,
  animate = true,
  compact = false,
  className = '',
}: StatWidgetProps) {
  const colors = colorMap[color]

  if (compact) {
    return (
      <div
        className={`
          p-4 rounded-lg
          bg-[#1a1a2e]/60 backdrop-blur-sm
          border border-[${colors.primary}]/20
          ${className}
        `}
      >
        <div className="flex items-center gap-2 text-[#a0a0b0] mb-1">
          {Icon && <Icon className="w-4 h-4" style={{ color: colors.primary }} />}
          <span className="text-xs font-mono uppercase tracking-wider">{title}</span>
        </div>
        <div className="flex items-baseline gap-1">
          <span
            className="text-2xl font-bold font-mono"
            style={{ color: colors.primary, textShadow: `0 0 10px ${colors.glow}` }}
          >
            {loading ? '---' : (
              <>
                {prefix}
                {typeof value === 'number' && animate ? (
                  <AnimatedNumber value={value} />
                ) : (
                  typeof value === 'number' ? value.toLocaleString() : value
                )}
                {suffix}
              </>
            )}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`
        relative p-6 rounded-xl overflow-hidden
        bg-gradient-to-br from-[#252538]/60 to-[#12121a]/80
        backdrop-blur-xl
        border border-[${colors.primary}]/20
        shadow-[0_0_20px_${colors.bg}]
        transition-all duration-300
        hover:border-[${colors.primary}]/40
        hover:shadow-[0_0_30px_${colors.bg}]
        ${className}
      `}
    >
      {/* Background glow */}
      <div
        className="absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl opacity-20 pointer-events-none"
        style={{ background: colors.primary }}
      />

      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          {Icon && (
            <div
              className="p-2 rounded-lg"
              style={{ background: colors.bg }}
            >
              <Icon
                className="w-5 h-5"
                style={{ color: colors.primary, filter: `drop-shadow(0 0 4px ${colors.glow})` }}
              />
            </div>
          )}
          <span className="text-sm font-mono uppercase tracking-wider text-[#a0a0b0]">
            {title}
          </span>
        </div>

        {/* Trend indicator */}
        {trend && (
          <div
            className={`
              flex items-center gap-1 px-2 py-1 rounded text-xs font-mono
              ${trend.isPositive ? 'bg-[#00ff88]/10 text-[#00ff88]' : 'bg-[#ff0044]/10 text-[#ff0044]'}
            `}
          >
            <span>{trend.isPositive ? '+' : ''}{trend.value}%</span>
            <svg
              className={`w-3 h-3 ${trend.isPositive ? '' : 'rotate-180'}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </div>
        )}
      </div>

      {/* Value */}
      <div className="mb-4">
        {loading ? (
          <div className="h-10 w-32 bg-[#252538] rounded animate-pulse shimmer" />
        ) : (
          <div className="flex items-baseline gap-2">
            <span
              className="text-4xl font-bold font-mono digital-number"
              style={{
                color: colors.primary,
                textShadow: `0 0 20px ${colors.glow}`,
              }}
            >
              {prefix}
              {typeof value === 'number' && animate ? (
                <AnimatedNumber value={value} />
              ) : (
                typeof value === 'number' ? value.toLocaleString() : value
              )}
            </span>
            {suffix && (
              <span className="text-lg text-[#606080] font-mono">{suffix}</span>
            )}
          </div>
        )}
      </div>

      {/* Sparkline */}
      {sparkline && sparkline.length > 0 && (
        <div className="mt-4">
          <Sparkline data={sparkline} color={colors.primary} />
        </div>
      )}

      {/* Decorative elements */}
      <div className="absolute bottom-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-[${colors.primary}]/30 to-transparent" />
    </div>
  )
}

// Grid wrapper for multiple stat widgets
interface StatGridProps {
  children: ReactNode
  columns?: 2 | 3 | 4
  className?: string
}

export function StatGrid({ children, columns = 4, className = '' }: StatGridProps) {
  const colsClass = {
    2: 'grid-cols-1 md:grid-cols-2',
    3: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
  }

  return (
    <div className={`grid ${colsClass[columns]} gap-6 ${className}`}>
      {children}
    </div>
  )
}
