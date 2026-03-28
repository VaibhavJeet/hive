'use client'

import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { API_BASE_URL } from '@/lib/api'

async function fetchActivity() {
  const res = await fetch(`${API_BASE_URL}/analytics/engagement?granularity=hour`)
  if (!res.ok) {
    throw new Error(`Failed to fetch activity data: ${res.status}`)
  }
  const data = await res.json()
  if (data.data_points && Array.isArray(data.data_points)) {
    return data.data_points.map((point: { label: string; likes: number; comments: number; shares: number }) => ({
      time: point.label,
      posts: point.shares || 0,
      likes: point.likes || 0,
      comments: point.comments || 0,
    }))
  }
  return []
}

export function ActivityChart() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['activity'],
    queryFn: fetchActivity,
    refetchInterval: 60000,
  })

  if (isLoading) {
    return <div className="h-64 flex items-center justify-center text-[#666666]">Loading...</div>
  }

  if (isError || !data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-[#666666]">
        No data available
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
        <XAxis dataKey="time" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="posts" stroke="#44ff88" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="likes" stroke="#ff00aa" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="comments" stroke="#00f0ff" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
