import { LucideIcon } from 'lucide-react'

interface StatsCardProps {
  title: string
  value: number | string
  icon: LucideIcon
  trend?: string
  subtitle?: string
  loading?: boolean
  compact?: boolean
}

export function StatsCard({
  title,
  value,
  icon: Icon,
  trend,
  subtitle,
  loading,
  compact
}: StatsCardProps) {
  if (compact) {
    return (
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="flex items-center gap-2 text-gray-600 mb-1">
          <Icon className="w-4 h-4" />
          <span className="text-sm">{title}</span>
        </div>
        <p className="text-2xl font-bold">
          {loading ? '...' : typeof value === 'number' ? value.toLocaleString() : value}
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-3xl font-bold mt-1">
            {loading ? '...' : typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          {subtitle && (
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
          )}
          {trend && (
            <p className={`text-sm mt-1 ${
              trend.startsWith('+') ? 'text-green-600' : 'text-red-600'
            }`}>
              {trend} from yesterday
            </p>
          )}
        </div>
        <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
          <Icon className="w-6 h-6 text-purple-600" />
        </div>
      </div>
    </div>
  )
}
