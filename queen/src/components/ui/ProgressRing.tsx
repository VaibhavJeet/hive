'use client'

import { useEffect, useState, ReactNode, useId } from 'react'

type RingColor = 'cyan' | 'magenta' | 'green' | 'amber' | 'purple' | 'gradient'
type RingSize = 'sm' | 'md' | 'lg' | 'xl'

interface ProgressRingProps {
  value: number
  max?: number
  color?: RingColor
  size?: RingSize
  strokeWidth?: number
  showLabel?: boolean
  label?: ReactNode
  animated?: boolean
  glowing?: boolean
  className?: string
}

const colorMap: Record<Exclude<RingColor, 'gradient'>, { primary: string; glow: string }> = {
  cyan: { primary: '#00f0ff', glow: 'rgba(0, 240, 255, 0.5)' },
  magenta: { primary: '#ff00aa', glow: 'rgba(255, 0, 170, 0.5)' },
  green: { primary: '#00ff88', glow: 'rgba(0, 255, 136, 0.5)' },
  amber: { primary: '#ffaa00', glow: 'rgba(255, 170, 0, 0.5)' },
  purple: { primary: '#aa00ff', glow: 'rgba(170, 0, 255, 0.5)' },
}

const sizeMap: Record<RingSize, { size: number; fontSize: string }> = {
  sm: { size: 60, fontSize: 'text-sm' },
  md: { size: 100, fontSize: 'text-xl' },
  lg: { size: 140, fontSize: 'text-2xl' },
  xl: { size: 180, fontSize: 'text-3xl' },
}

export function ProgressRing({
  value,
  max = 100,
  color = 'cyan',
  size = 'md',
  strokeWidth = 8,
  showLabel = true,
  label,
  animated = true,
  glowing = true,
  className = '',
}: ProgressRingProps) {
  const percentage = Math.min((value / max) * 100, 100)
  const [animatedValue, setAnimatedValue] = useState(animated ? 0 : percentage)
  const sizeConfig = sizeMap[size]
  const radius = (sizeConfig.size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const strokeDashoffset = circumference - (animatedValue / 100) * circumference

  useEffect(() => {
    if (!animated) {
      setAnimatedValue(percentage)
      return
    }

    const duration = 1000
    const startTime = Date.now()
    const startValue = animatedValue
    let animationId: number

    const animate = () => {
      const elapsed = Date.now() - startTime
      const progress = Math.min(elapsed / duration, 1)
      const easeOut = 1 - Math.pow(1 - progress, 3)
      setAnimatedValue(startValue + (percentage - startValue) * easeOut)

      if (progress < 1) {
        animationId = requestAnimationFrame(animate)
      }
    }

    animationId = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animationId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [percentage, animated])

  const isGradient = color === 'gradient'
  const colors = isGradient ? null : colorMap[color]
  const uniqueId = useId()
  const gradientId = `progress-gradient-${uniqueId.replace(/:/g, '-')}`

  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: sizeConfig.size, height: sizeConfig.size }}
    >
      <svg
        className="progress-ring"
        width={sizeConfig.size}
        height={sizeConfig.size}
      >
        {/* Gradient definition */}
        {isGradient && (
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00f0ff" />
              <stop offset="50%" stopColor="#ff00aa" />
              <stop offset="100%" stopColor="#00ff88" />
            </linearGradient>
          </defs>
        )}

        {/* Background circle */}
        <circle
          cx={sizeConfig.size / 2}
          cy={sizeConfig.size / 2}
          r={radius}
          fill="none"
          stroke="#252538"
          strokeWidth={strokeWidth}
        />

        {/* Background glow circle (subtle) */}
        <circle
          cx={sizeConfig.size / 2}
          cy={sizeConfig.size / 2}
          r={radius}
          fill="none"
          stroke={colors?.primary || '#00f0ff'}
          strokeWidth={strokeWidth}
          strokeOpacity={0.1}
        />

        {/* Progress circle */}
        <circle
          cx={sizeConfig.size / 2}
          cy={sizeConfig.size / 2}
          r={radius}
          fill="none"
          stroke={isGradient ? `url(#${gradientId})` : colors?.primary}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{
            transition: animated ? 'none' : 'stroke-dashoffset 0.5s ease',
            filter: glowing
              ? `drop-shadow(0 0 ${strokeWidth}px ${colors?.glow || 'rgba(0, 240, 255, 0.5)'})`
              : 'none',
          }}
        />

        {/* Animated endpoint glow */}
        {glowing && animatedValue > 0 && (
          <circle
            cx={sizeConfig.size / 2 + radius * Math.cos(((animatedValue / 100) * 360 - 90) * (Math.PI / 180))}
            cy={sizeConfig.size / 2 + radius * Math.sin(((animatedValue / 100) * 360 - 90) * (Math.PI / 180))}
            r={strokeWidth / 2 + 2}
            fill={colors?.primary || '#00f0ff'}
            style={{
              filter: `drop-shadow(0 0 ${strokeWidth * 2}px ${colors?.glow || 'rgba(0, 240, 255, 0.8)'})`,
            }}
          />
        )}
      </svg>

      {/* Center label */}
      {showLabel && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {label || (
            <>
              <span
                className={`font-mono font-bold ${sizeConfig.fontSize}`}
                style={{
                  color: colors?.primary || '#00f0ff',
                  textShadow: glowing ? `0 0 10px ${colors?.glow || 'rgba(0, 240, 255, 0.5)'}` : 'none',
                }}
              >
                {Math.round(animatedValue)}%
              </span>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// Multi-ring progress (nested rings)
interface MultiRingProps {
  rings: Array<{
    value: number
    max?: number
    color: Exclude<RingColor, 'gradient'>
    label?: string
  }>
  size?: RingSize
  className?: string
}

export function MultiProgressRing({ rings, size = 'lg', className = '' }: MultiRingProps) {
  const sizeConfig = sizeMap[size]
  const baseStrokeWidth = 6
  const ringGap = 4

  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: sizeConfig.size, height: sizeConfig.size }}
    >
      {rings.map((ring, index) => {
        const strokeWidth = baseStrokeWidth
        const offset = index * (strokeWidth + ringGap)
        const adjustedSize = sizeConfig.size - offset * 2
        const colors = colorMap[ring.color]
        const radius = (adjustedSize - strokeWidth) / 2
        const circumference = radius * 2 * Math.PI
        const percentage = Math.min((ring.value / (ring.max || 100)) * 100, 100)
        const strokeDashoffset = circumference - (percentage / 100) * circumference

        return (
          <svg
            key={index}
            className="absolute progress-ring"
            width={adjustedSize}
            height={adjustedSize}
            style={{
              top: offset,
              left: offset,
            }}
          >
            {/* Background */}
            <circle
              cx={adjustedSize / 2}
              cy={adjustedSize / 2}
              r={radius}
              fill="none"
              stroke="#252538"
              strokeWidth={strokeWidth}
            />

            {/* Progress */}
            <circle
              cx={adjustedSize / 2}
              cy={adjustedSize / 2}
              r={radius}
              fill="none"
              stroke={colors.primary}
              strokeWidth={strokeWidth}
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              style={{
                filter: `drop-shadow(0 0 ${strokeWidth}px ${colors.glow})`,
                transition: 'stroke-dashoffset 1s ease',
              }}
            />
          </svg>
        )
      })}

      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-center">
          {rings.map((ring, index) => (
            <div key={index} className="flex items-center gap-2 text-xs">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: colorMap[ring.color].primary }}
              />
              <span className="text-[#a0a0b0]">{ring.label || `Ring ${index + 1}`}</span>
              <span style={{ color: colorMap[ring.color].primary }}>
                {Math.round((ring.value / (ring.max || 100)) * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
