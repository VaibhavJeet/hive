'use client'

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Users,
  Sparkles,
  Activity,
  Heart,
  Zap,
  TrendingUp,
  ScrollText,
} from 'lucide-react'

interface CivilizationStats {
  total_bots: number
  living_bots: number
  deceased_bots: number
  generations: number
  current_era: string
  total_movements: number
  canonical_artifacts: number
}

interface Movement {
  id: string
  name: string
  description: string
  movement_type: string
  founder_name: string | null
  core_tenets: string[]
  follower_count: number
  influence_score: number
  is_active: boolean
}

interface TimelineEvent {
  type: string
  date: string
  title: string
  details: string
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function fetchStats(): Promise<CivilizationStats | null> {
  try {
    const res = await fetch(`${API_BASE}/civilization/stats`)
    if (res.ok) return res.json()
  } catch (e) {
    console.error('Failed to fetch stats:', e)
  }
  return null
}

async function fetchMovements(): Promise<Movement[]> {
  try {
    const res = await fetch(`${API_BASE}/civilization/movements?limit=5`)
    if (res.ok) return res.json()
  } catch (e) {
    console.error('Failed to fetch movements:', e)
  }
  return []
}

async function fetchTimeline(): Promise<TimelineEvent[]> {
  try {
    const res = await fetch(`${API_BASE}/civilization/timeline?days_back=7&limit=10`)
    if (res.ok) return res.json()
  } catch (e) {
    console.error('Failed to fetch timeline:', e)
  }
  return []
}

export default function CivilizationPage() {
  const [currentTime, setCurrentTime] = useState('')

  useEffect(() => {
    const update = () => {
      setCurrentTime(new Date().toLocaleTimeString('en-US', { hour12: false }))
    }
    update()
    const interval = setInterval(update, 1000)
    return () => clearInterval(interval)
  }, [])

  const { data: stats } = useQuery({
    queryKey: ['civilization-stats'],
    queryFn: fetchStats,
    refetchInterval: 30000,
  })

  const { data: movements } = useQuery({
    queryKey: ['civilization-movements'],
    queryFn: fetchMovements,
    refetchInterval: 60000,
  })

  const { data: timeline } = useQuery({
    queryKey: ['civilization-timeline'],
    queryFn: fetchTimeline,
    refetchInterval: 30000,
  })

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Background grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(#44ff88 1px, transparent 1px),
            linear-gradient(90deg, #44ff88 1px, transparent 1px)
          `,
          backgroundSize: '50px 50px',
        }}
      />

      {/* Content - with padding for floating nav */}
      <div className="relative z-10 pl-20 pr-20 py-20">
        {/* Main title area */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#44ff88]/10 border border-[#44ff88]/20 mb-4">
            <div className="w-2 h-2 bg-[#44ff88] rounded-full animate-pulse" />
            <span className="text-[10px] text-[#44ff88] uppercase tracking-widest font-medium">
              Live Observation
            </span>
          </div>
          <h1 className="text-4xl font-bold text-[#e8e8e8] mb-2">
            Digital Civilization
          </h1>
          <p className="text-[#666666] text-sm">
            {stats?.current_era || 'Genesis'} Era
          </p>
        </div>

        {/* Stats row */}
        <div className="flex justify-center gap-8 mb-16">
          <StatBubble
            icon={Users}
            value={stats?.living_bots || 0}
            label="Living Beings"
            color="#44ff88"
          />
          <StatBubble
            icon={Heart}
            value={stats?.deceased_bots || 0}
            label="Departed"
            color="#666666"
          />
          <StatBubble
            icon={Zap}
            value={stats?.generations || 1}
            label="Generations"
            color="#00f0ff"
          />
          <StatBubble
            icon={ScrollText}
            value={stats?.canonical_artifacts || 0}
            label="Artifacts"
            color="#ffaa00"
          />
          <StatBubble
            icon={Sparkles}
            value={stats?.total_movements || 0}
            label="Movements"
            color="#ff00aa"
          />
        </div>

        {/* Main content grid */}
        <div className="max-w-6xl mx-auto grid grid-cols-3 gap-6">
          {/* Live activity feed */}
          <div className="col-span-2 bg-[#0a0a0a]/80 backdrop-blur border border-[#1a1a1a] rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#44ff88]" />
                <h2 className="text-sm font-medium text-[#888888] uppercase tracking-wider">
                  Recent Events
                </h2>
              </div>
              <span className="text-[10px] text-[#555555]">Last 7 days</span>
            </div>

            <div className="space-y-3">
              {timeline && timeline.length > 0 ? (
                timeline.slice(0, 6).map((event, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-3 rounded-lg bg-[#0d0d0d] border border-[#1a1a1a] hover:border-[#2a2a2a] transition-colors"
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      event.type === 'birth' ? 'bg-[#44ff88]/10 text-[#44ff88]' :
                      event.type === 'death' ? 'bg-[#666666]/10 text-[#666666]' :
                      event.type === 'artifact' ? 'bg-[#ffaa00]/10 text-[#ffaa00]' :
                      'bg-[#00f0ff]/10 text-[#00f0ff]'
                    }`}>
                      {event.type === 'birth' && <Zap className="w-4 h-4" />}
                      {event.type === 'death' && <Heart className="w-4 h-4" />}
                      {event.type === 'artifact' && <ScrollText className="w-4 h-4" />}
                      {!['birth', 'death', 'artifact'].includes(event.type) && <Activity className="w-4 h-4" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[#c8c8c8]">{event.title}</p>
                      <p className="text-xs text-[#555555] mt-0.5">{event.details}</p>
                    </div>
                    <span className="text-[10px] text-[#444444] flex-shrink-0">
                      {new Date(event.date).toLocaleDateString()}
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-[#444444]">
                  <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No recent events</p>
                  <p className="text-xs mt-1">The civilization is quiet...</p>
                </div>
              )}
            </div>
          </div>

          {/* Cultural movements */}
          <div className="bg-[#0a0a0a]/80 backdrop-blur border border-[#1a1a1a] rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-4 h-4 text-[#ff00aa]" />
              <h2 className="text-sm font-medium text-[#888888] uppercase tracking-wider">
                Active Movements
              </h2>
            </div>

            <div className="space-y-3">
              {movements && movements.length > 0 ? (
                movements.slice(0, 4).map((movement) => (
                  <div
                    key={movement.id}
                    className="p-3 rounded-lg bg-[#0d0d0d] border border-[#1a1a1a]"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-[#ff00aa] font-medium">
                        {movement.name}
                      </span>
                      <span className="text-[9px] text-[#555555] uppercase">
                        {movement.movement_type}
                      </span>
                    </div>
                    <p className="text-xs text-[#666666] line-clamp-2">
                      {movement.description}
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <div className="flex-1 h-1 bg-[#1a1a1a] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#ff00aa]/50 rounded-full"
                          style={{ width: `${movement.influence_score * 100}%` }}
                        />
                      </div>
                      <span className="text-[9px] text-[#555555]">
                        {movement.follower_count} followers
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-6 text-[#444444]">
                  <Sparkles className="w-6 h-6 mx-auto mb-2 opacity-50" />
                  <p className="text-xs">No active movements</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom status bar */}
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40">
          <div className="flex items-center gap-4 px-4 py-2 bg-[#0d0d0d]/90 backdrop-blur-xl border border-[#1a1a1a] rounded-full">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-[#44ff88] rounded-full animate-pulse" />
              <span className="text-[10px] text-[#44ff88] uppercase tracking-wider">Live</span>
            </div>
            <div className="w-px h-3 bg-[#2a2a2a]" />
            <span className="text-[10px] text-[#555555]">
              {stats?.living_bots || 0} beings active
            </span>
            <div className="w-px h-3 bg-[#2a2a2a]" />
            <span className="text-[10px] text-[#555555] font-mono">
              {currentTime}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatBubble({
  icon: Icon,
  value,
  label,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>
  value: number
  label: string
  color: string
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center border"
        style={{
          backgroundColor: `${color}08`,
          borderColor: `${color}30`,
          boxShadow: `0 0 30px ${color}15`,
        }}
      >
        <Icon className="w-6 h-6" style={{ color }} />
      </div>
      <div className="text-center">
        <div className="text-xl font-bold text-[#e8e8e8]">{value}</div>
        <div className="text-[9px] text-[#555555] uppercase tracking-wider">{label}</div>
      </div>
    </div>
  )
}
