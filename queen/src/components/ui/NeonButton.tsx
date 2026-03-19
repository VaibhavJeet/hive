'use client'

import { ReactNode, ButtonHTMLAttributes } from 'react'

type NeonColor = 'cyan' | 'magenta' | 'green' | 'amber' | 'purple' | 'red'
type ButtonSize = 'sm' | 'md' | 'lg'
type ButtonVariant = 'solid' | 'outline' | 'ghost'

interface NeonButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  color?: NeonColor
  size?: ButtonSize
  variant?: ButtonVariant
  glowing?: boolean
  loading?: boolean
  icon?: ReactNode
  iconPosition?: 'left' | 'right'
}

const colorMap: Record<NeonColor, {
  solid: string;
  outline: string;
  ghost: string;
  glow: string;
}> = {
  cyan: {
    solid: 'bg-[#00f0ff] text-[#0a0a0f] hover:bg-[#00f0ff]/90',
    outline: 'border-[#00f0ff] text-[#00f0ff] hover:bg-[#00f0ff]/10',
    ghost: 'text-[#00f0ff] hover:bg-[#00f0ff]/10',
    glow: 'shadow-[0_0_20px_rgba(0,240,255,0.5)] hover:shadow-[0_0_30px_rgba(0,240,255,0.7)]',
  },
  magenta: {
    solid: 'bg-[#ff00aa] text-white hover:bg-[#ff00aa]/90',
    outline: 'border-[#ff00aa] text-[#ff00aa] hover:bg-[#ff00aa]/10',
    ghost: 'text-[#ff00aa] hover:bg-[#ff00aa]/10',
    glow: 'shadow-[0_0_20px_rgba(255,0,170,0.5)] hover:shadow-[0_0_30px_rgba(255,0,170,0.7)]',
  },
  green: {
    solid: 'bg-[#00ff88] text-[#0a0a0f] hover:bg-[#00ff88]/90',
    outline: 'border-[#00ff88] text-[#00ff88] hover:bg-[#00ff88]/10',
    ghost: 'text-[#00ff88] hover:bg-[#00ff88]/10',
    glow: 'shadow-[0_0_20px_rgba(0,255,136,0.5)] hover:shadow-[0_0_30px_rgba(0,255,136,0.7)]',
  },
  amber: {
    solid: 'bg-[#ffaa00] text-[#0a0a0f] hover:bg-[#ffaa00]/90',
    outline: 'border-[#ffaa00] text-[#ffaa00] hover:bg-[#ffaa00]/10',
    ghost: 'text-[#ffaa00] hover:bg-[#ffaa00]/10',
    glow: 'shadow-[0_0_20px_rgba(255,170,0,0.5)] hover:shadow-[0_0_30px_rgba(255,170,0,0.7)]',
  },
  purple: {
    solid: 'bg-[#aa00ff] text-white hover:bg-[#aa00ff]/90',
    outline: 'border-[#aa00ff] text-[#aa00ff] hover:bg-[#aa00ff]/10',
    ghost: 'text-[#aa00ff] hover:bg-[#aa00ff]/10',
    glow: 'shadow-[0_0_20px_rgba(170,0,255,0.5)] hover:shadow-[0_0_30px_rgba(170,0,255,0.7)]',
  },
  red: {
    solid: 'bg-[#ff0044] text-white hover:bg-[#ff0044]/90',
    outline: 'border-[#ff0044] text-[#ff0044] hover:bg-[#ff0044]/10',
    ghost: 'text-[#ff0044] hover:bg-[#ff0044]/10',
    glow: 'shadow-[0_0_20px_rgba(255,0,68,0.5)] hover:shadow-[0_0_30px_rgba(255,0,68,0.7)]',
  },
}

const sizeMap: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export function NeonButton({
  children,
  color = 'cyan',
  size = 'md',
  variant = 'solid',
  glowing = false,
  loading = false,
  icon,
  iconPosition = 'left',
  className = '',
  disabled,
  ...props
}: NeonButtonProps) {
  const colors = colorMap[color]
  const sizeClass = sizeMap[size]

  const baseClasses = `
    relative inline-flex items-center justify-center gap-2
    font-mono font-medium tracking-wider uppercase
    rounded-lg
    transition-all duration-300 ease-out
    focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0a0a0f]
    disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:transform-none
  `

  const variantClasses = {
    solid: `${colors.solid} border-0`,
    outline: `${colors.outline} border-2 bg-transparent`,
    ghost: `${colors.ghost} border-0 bg-transparent`,
  }

  const glowClass = glowing ? colors.glow : ''

  const hoverTransform = disabled ? '' : 'hover:scale-[1.02] active:scale-[0.98]'

  return (
    <button
      className={`
        ${baseClasses}
        ${variantClasses[variant]}
        ${sizeClass}
        ${glowClass}
        ${hoverTransform}
        ${className}
      `}
      disabled={disabled || loading}
      {...props}
    >
      {/* Loading spinner */}
      {loading && (
        <svg
          className="animate-spin h-4 w-4"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}

      {/* Icon left */}
      {!loading && icon && iconPosition === 'left' && (
        <span className="flex-shrink-0">{icon}</span>
      )}

      {/* Button text */}
      <span>{children}</span>

      {/* Icon right */}
      {!loading && icon && iconPosition === 'right' && (
        <span className="flex-shrink-0">{icon}</span>
      )}

      {/* Animated border glow effect for outline variant */}
      {variant === 'outline' && (
        <span className="absolute inset-0 rounded-lg overflow-hidden pointer-events-none">
          <span className="absolute inset-[-1000%] animate-[spin_3s_linear_infinite] bg-[conic-gradient(from_90deg_at_50%_50%,#00f0ff_0%,#ff00aa_50%,#00f0ff_100%)] opacity-0 group-hover:opacity-30" />
        </span>
      )}
    </button>
  )
}

// Icon-only button variant
interface IconButtonProps extends Omit<NeonButtonProps, 'children' | 'icon' | 'iconPosition'> {
  icon: ReactNode
  'aria-label': string
}

export function NeonIconButton({
  icon,
  size = 'md',
  className = '',
  ...props
}: IconButtonProps) {
  const sizeMap: Record<ButtonSize, string> = {
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
  }

  return (
    <NeonButton
      size={size}
      className={`${sizeMap[size]} !p-0 ${className}`}
      {...props}
    >
      {icon}
    </NeonButton>
  )
}
