'use client'

import { ReactNode } from 'react'

interface Column<T> {
  key: keyof T | string
  header: string
  width?: string
  align?: 'left' | 'center' | 'right'
  render?: (value: unknown, row: T, index: number) => ReactNode
}

interface DataGridProps<T> {
  data: T[]
  columns: Column<T>[]
  className?: string
  loading?: boolean
  emptyMessage?: string
  onRowClick?: (row: T, index: number) => void
  selectedIndex?: number
  striped?: boolean
  compact?: boolean
  maxHeight?: string
}

export function DataGrid<T extends Record<string, unknown>>({
  data,
  columns,
  className = '',
  loading = false,
  emptyMessage = 'No data available',
  onRowClick,
  selectedIndex,
  striped = false,
  compact = false,
  maxHeight = '400px',
}: DataGridProps<T>) {
  const cellPadding = compact ? 'px-3 py-2' : 'px-4 py-3'
  const fontSize = compact ? 'text-xs' : 'text-sm'

  const getNestedValue = (obj: T, key: string): unknown => {
    return key.split('.').reduce((acc: unknown, part) => {
      if (acc && typeof acc === 'object' && part in acc) {
        return (acc as Record<string, unknown>)[part]
      }
      return undefined
    }, obj)
  }

  return (
    <div
      className={`
        relative rounded-lg overflow-hidden
        bg-[#12121a]/80 backdrop-blur-sm
        border border-[#00f0ff]/20
        ${className}
      `}
    >
      {/* Futuristic corner accents */}
      <div className="absolute top-0 left-0 w-8 h-[2px] bg-gradient-to-r from-[#00f0ff] to-transparent" />
      <div className="absolute top-0 left-0 w-[2px] h-8 bg-gradient-to-b from-[#00f0ff] to-transparent" />
      <div className="absolute top-0 right-0 w-8 h-[2px] bg-gradient-to-l from-[#ff00aa] to-transparent" />
      <div className="absolute top-0 right-0 w-[2px] h-8 bg-gradient-to-b from-[#ff00aa] to-transparent" />
      <div className="absolute bottom-0 left-0 w-8 h-[2px] bg-gradient-to-r from-[#00f0ff] to-transparent" />
      <div className="absolute bottom-0 left-0 w-[2px] h-8 bg-gradient-to-t from-[#00f0ff] to-transparent" />
      <div className="absolute bottom-0 right-0 w-8 h-[2px] bg-gradient-to-l from-[#ff00aa] to-transparent" />
      <div className="absolute bottom-0 right-0 w-[2px] h-8 bg-gradient-to-t from-[#ff00aa] to-transparent" />

      <div className="overflow-auto" style={{ maxHeight }}>
        <table className="w-full">
          {/* Header */}
          <thead className="sticky top-0 z-10">
            <tr className="bg-[#1a1a2e]/95 backdrop-blur-sm border-b border-[#00f0ff]/30">
              {columns.map((column, idx) => (
                <th
                  key={idx}
                  className={`
                    ${cellPadding} ${fontSize}
                    font-mono font-semibold uppercase tracking-wider
                    text-[#00f0ff]
                    text-${column.align || 'left'}
                    whitespace-nowrap
                  `}
                  style={{ width: column.width }}
                >
                  <span className="flex items-center gap-2">
                    <span className="w-1 h-1 rounded-full bg-[#00f0ff] animate-pulse" />
                    {column.header}
                  </span>
                </th>
              ))}
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {loading ? (
              // Loading skeleton
              Array.from({ length: 5 }).map((_, idx) => (
                <tr key={idx} className="border-b border-[#252538]/50">
                  {columns.map((_, colIdx) => (
                    <td key={colIdx} className={cellPadding}>
                      <div className="h-4 bg-[#252538] rounded animate-pulse shimmer" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              // Empty state
              <tr>
                <td
                  colSpan={columns.length}
                  className="text-center py-12 text-[#606080]"
                >
                  <div className="flex flex-col items-center gap-3">
                    <svg
                      className="w-12 h-12 text-[#606080]/50"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                      />
                    </svg>
                    <span className="font-mono text-sm">{emptyMessage}</span>
                  </div>
                </td>
              </tr>
            ) : (
              // Data rows
              data.map((row, rowIdx) => (
                <tr
                  key={rowIdx}
                  onClick={() => onRowClick?.(row, rowIdx)}
                  className={`
                    border-b border-[#252538]/30
                    transition-all duration-200
                    ${onRowClick ? 'cursor-pointer' : ''}
                    ${selectedIndex === rowIdx
                      ? 'bg-[#00f0ff]/10 border-l-2 border-l-[#00f0ff]'
                      : striped && rowIdx % 2 === 1
                        ? 'bg-[#1a1a2e]/30'
                        : 'bg-transparent'
                    }
                    hover:bg-[#00f0ff]/5
                  `}
                >
                  {columns.map((column, colIdx) => {
                    const value = getNestedValue(row, column.key as string)
                    return (
                      <td
                        key={colIdx}
                        className={`
                          ${cellPadding} ${fontSize}
                          text-[#e0e0e0]
                          text-${column.align || 'left'}
                        `}
                      >
                        {column.render
                          ? column.render(value, row, rowIdx)
                          : String(value ?? '-')}
                      </td>
                    )
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Footer info bar */}
      {!loading && data.length > 0 && (
        <div className="px-4 py-2 bg-[#1a1a2e]/50 border-t border-[#252538]/50 flex items-center justify-between">
          <span className="text-xs text-[#606080] font-mono">
            {data.length} record{data.length !== 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-2 text-xs text-[#606080]">
            <span className="w-2 h-2 rounded-full bg-[#00ff88] animate-pulse" />
            LIVE DATA
          </span>
        </div>
      )}
    </div>
  )
}

// Helper component for status cells
interface StatusCellProps {
  status: 'online' | 'offline' | 'warning' | 'error' | 'pending'
  label?: string
}

export function StatusCell({ status, label }: StatusCellProps) {
  const statusConfig = {
    online: { color: '#00ff88', text: label || 'Online' },
    offline: { color: '#606080', text: label || 'Offline' },
    warning: { color: '#ffaa00', text: label || 'Warning' },
    error: { color: '#ff0044', text: label || 'Error' },
    pending: { color: '#00f0ff', text: label || 'Pending' },
  }

  const config = statusConfig[status]

  return (
    <span className="inline-flex items-center gap-2">
      <span
        className="w-2 h-2 rounded-full animate-pulse"
        style={{ backgroundColor: config.color, boxShadow: `0 0 8px ${config.color}` }}
      />
      <span style={{ color: config.color }}>{config.text}</span>
    </span>
  )
}

// Helper component for progress cells
interface ProgressCellProps {
  value: number
  max?: number
  showLabel?: boolean
}

export function ProgressCell({ value, max = 100, showLabel = true }: ProgressCellProps) {
  const percentage = Math.min((value / max) * 100, 100)
  const color = percentage > 80 ? '#ff0044' : percentage > 60 ? '#ffaa00' : '#00ff88'

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-[#252538] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${percentage}%`,
            background: `linear-gradient(90deg, ${color}, ${color}80)`,
            boxShadow: `0 0 10px ${color}50`,
          }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-mono" style={{ color }}>
          {Math.round(percentage)}%
        </span>
      )}
    </div>
  )
}
