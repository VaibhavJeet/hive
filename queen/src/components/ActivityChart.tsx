'use client'

import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

async function fetchActivity() {
  const res = await fetch('/api/analytics/engagement?granularity=hour')
  if (!res.ok) {
    return generateMockData()
  }
  return res.json()
}

function generateMockData() {
  const hours = []
  for (let i = 23; i >= 0; i--) {
    const hour = new Date()
    hour.setHours(hour.getHours() - i)
    hours.push({
      time: hour.toLocaleTimeString('en-US', { hour: '2-digit' }),
      posts: Math.floor(Math.random() * 10) + 1,
      likes: Math.floor(Math.random() * 30) + 5,
      comments: Math.floor(Math.random() * 15) + 2,
    })
  }
  return hours
}

export function ActivityChart() {
  const { data, isLoading } = useQuery({
    queryKey: ['activity'],
    queryFn: fetchActivity,
    refetchInterval: 60000,
  })

  if (isLoading) {
    return <div className="h-64 flex items-center justify-center text-gray-500">Loading...</div>
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="time" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="posts" stroke="#8b5cf6" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="likes" stroke="#ec4899" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="comments" stroke="#06b6d4" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
