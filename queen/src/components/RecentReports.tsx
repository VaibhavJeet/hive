'use client'

import { useQuery } from '@tanstack/react-query'
import { CheckCircle, Clock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface Report {
  id: string
  report_type: string
  status: string
  reason: string
  created_at: string
}

async function fetchReports(): Promise<Report[]> {
  const res = await fetch('/api/reports?limit=5')
  if (!res.ok) return []
  const data = await res.json()
  return data.reports || []
}

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  reviewed: 'bg-blue-100 text-blue-700',
  resolved: 'bg-green-100 text-green-700',
  dismissed: 'bg-gray-100 text-gray-700',
}

const typeIcons: Record<string, string> = {
  spam: '🚫',
  harassment: '⚠️',
  inappropriate: '🔞',
  other: '📝',
}

export function RecentReports() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: fetchReports,
    refetchInterval: 30000,
  })

  if (isLoading) {
    return <div className="text-gray-500">Loading reports...</div>
  }

  if (!reports?.length) {
    return (
      <div className="text-center py-8 text-gray-500">
        <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
        <p>No pending reports</p>
      </div>
    )
  }

  return (
    <div className="space-y-3 max-h-64 overflow-y-auto">
      {reports.map((report) => (
        <div key={report.id} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
          <span className="text-xl">
            {typeIcons[report.report_type] || '📝'}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                statusColors[report.status] || statusColors.pending
              }`}>
                {report.status}
              </span>
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatDistanceToNow(new Date(report.created_at), { addSuffix: true })}
              </span>
            </div>
            <p className="text-sm mt-1 truncate">{report.reason}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
