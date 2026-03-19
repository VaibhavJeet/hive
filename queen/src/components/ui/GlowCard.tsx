'use client'

import { ReactNode } from 'react'

type GlowColor = 'cyan' | 'magenta' | 'green' | 'amber' | 'purple'

interface GlowCardProps {
  children: ReactNode
  className?: string
  glowColor?: GlowColor
  hoverable?: boolean
  animated?: boolean
  intensity?: 'low' | 'medium' | 'high'
  variant?: 'default' | 'outlined' | 'gradient'
}

const glowColorMap: Record<GlowColor, { border: string; shadow: string; bg: string }> = {
  cyan: {
    border: 'border-[#00f0ff]/30',
    shadow: 'shadow-[0_0_20px_rgba(0,240,255,0.15)]',
    bg: 'from-[#00f0ff]/10',
  },
  magenta: {
    border: 'border-[#ff00aa]/30',
    shadow: 'shadow-[0_0_20px_rgba(255,0,170,0.15)]',
    bg: 'from-[#ff00aa]/10',
  },
  green: {
    border: 'border-[#00ff88]/30',
    shadow: 'shadow-[0_0_20px_rgba(0,255,136,0.15)]',
    bg: 'from-[#00ff88]/10',
  },
  amber: {
    border: 'border-[#ffaa00]/30',
    shadow: 'shadow-[0_0_20px_rgba(255,170,0,0.15)]',
    bg: 'from-[#ffaa00]/10',
  },
  purple: {
    border: 'border-[#aa00ff]/30',
    shadow: 'shadow-[0_0_20px_rgba(170,0,255,0.15)]',
    bg: 'from-[#aa00ff]/10',
  },
}

const intensityMap = {
  low: 'opacity-50',
  medium: 'opacity-75',
  high: 'opacity-100',
}

export function GlowCard({
  children,
  className = '',
  glowColor = 'cyan',
  hoverable = true,
  animated = false,
  intensity = 'medium',
  variant = 'default',
}: GlowCardProps) {
  const colors = glowColorMap[glowColor]
  const intensityClass = intensityMap[intensity]

  const baseClasses = `
    relative overflow-hidden rounded-xl
    bg-gradient-to-br from-[#252538]/80 to-[#12121a]/90
    backdrop-blur-xl
    border ${colors.border}
    ${colors.shadow}
    ${intensityClass}
  `

  const hoverClasses = hoverable
    ? `
      transition-all duration-300 ease-out
      hover:translate-y-[-2px]
      hover:shadow-[0_0_30px_rgba(0,240,255,0.25)]
      hover:border-[#00f0ff]/50
    `
    : ''

  const animatedClasses = animated ? 'pulse-animation' : ''

  const variantClasses = {
    default: '',
    outlined: 'bg-transparent border-2',
    gradient: `bg-gradient-to-br ${colors.bg} to-transparent`,
  }

  return (
    <div
      className={`
        ${baseClasses}
        ${hoverClasses}
        ${animatedClasses}
        ${variantClasses[variant]}
        ${className}
      `}
    >
      {/* Subtle inner glow effect */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.03] to-transparent pointer-events-none" />

      {/* Corner decorations */}
      <div className="absolute top-0 left-0 w-4 h-4 border-t border-l border-[#00f0ff]/30" />
      <div className="absolute top-0 right-0 w-4 h-4 border-t border-r border-[#00f0ff]/30" />
      <div className="absolute bottom-0 left-0 w-4 h-4 border-b border-l border-[#00f0ff]/30" />
      <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r border-[#00f0ff]/30" />

      {/* Content */}
      <div className="relative z-10">{children}</div>
    </div>
  )
}

// Preset variants for common use cases
export function GlowCardCyan(props: Omit<GlowCardProps, 'glowColor'>) {
  return <GlowCard {...props} glowColor="cyan" />
}

export function GlowCardMagenta(props: Omit<GlowCardProps, 'glowColor'>) {
  return <GlowCard {...props} glowColor="magenta" />
}

export function GlowCardGreen(props: Omit<GlowCardProps, 'glowColor'>) {
  return <GlowCard {...props} glowColor="green" />
}

export function GlowCardAmber(props: Omit<GlowCardProps, 'glowColor'>) {
  return <GlowCard {...props} glowColor="amber" />
}
