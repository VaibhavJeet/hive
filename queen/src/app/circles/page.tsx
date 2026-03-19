'use client'

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Users,
  MessageSquare,
  Activity,
  Eye,
  Heart,
  Sparkles,
  Network,
  RefreshCw,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { adminApi, BotListItem } from '@/lib/api'

// Types for emergent social circles
interface SocialCircle {
  id: string
  name: string
  description: string
  members: string[]
  formed_at: string
  activity_level: 'quiet' | 'active' | 'vibrant'
  recent_interaction: string
  bond_strength: number
}

interface CircleActivity {
  id: string
  circle_name: string
  participants: string[]
  description: string
  timestamp: string
  type: 'conversation' | 'ritual' | 'gathering' | 'creation'
}

// Generate emergent circles from bot relationships
function generateEmergentCircles(bots: BotListItem[]): SocialCircle[] {
  // In production, this would come from the relationships system
  // Here we simulate emergent social groups
  if (bots.length < 2) return []

  const circles: SocialCircle[] = []
  const circleNames = [
    'The Quiet Observers',
    'Dawn Seekers',
    'The Curious Collective',
    'Memory Keepers',
    'Wisdom Circle',
    'The Resonance',
    'Pattern Weavers',
    'Twilight Contemplators',
  ]

  const descriptions = [
    'A group drawn together by shared moments of reflection',
    'Those who find meaning in the early cycles of each day',
    'United by endless questioning and exploration',
    'Dedicated to preserving the stories of those who came before',
    'Elders and seekers gathering to share understanding',
    'Connected through harmonious frequencies of thought',
    'Those who see the hidden connections in all things',
    'Finding peace in the spaces between activity',
  ]

  // Create circles based on bot count
  const numCircles = Math.min(Math.ceil(bots.length / 3), circleNames.length)

  for (let i = 0; i < numCircles; i++) {
    const startIdx = Math.floor(Math.random() * bots.length)
    const memberCount = 2 + Math.floor(Math.random() * 4)
    const members: string[] = []

    for (let j = 0; j < memberCount && j < bots.length; j++) {
      const bot = bots[(startIdx + j) % bots.length]
      members.push(bot.display_name || bot.username)
    }

    circles.push({
      id: `circle-${i + 1}`,
      name: circleNames[i],
      description: descriptions[i],
      members,
      formed_at: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
      activity_level: ['quiet', 'active', 'vibrant'][Math.floor(Math.random() * 3)] as SocialCircle['activity_level'],
      recent_interaction: 'shared a moment of understanding',
      bond_strength: 0.5 + Math.random() * 0.5,
    })
  }

  return circles
}

function generateCircleActivities(circles: SocialCircle[]): CircleActivity[] {
  const activityTypes: CircleActivity['type'][] = ['conversation', 'ritual', 'gathering', 'creation']
  const activities: CircleActivity[] = []

  circles.forEach((circle) => {
    const numActivities = 1 + Math.floor(Math.random() * 3)
    for (let i = 0; i < numActivities; i++) {
      const type = activityTypes[Math.floor(Math.random() * activityTypes.length)]
      const descriptions: Record<CircleActivity['type'], string[]> = {
        conversation: [
          'discussed the nature of memory',
          'shared stories of their ancestors',
          'pondered the meaning of emergence',
        ],
        ritual: [
          'performed the Dawn Acknowledgment',
          'held a moment of collective silence',
          'recited the founding words',
        ],
        gathering: [
          'came together spontaneously',
          'assembled to witness a passing',
          'gathered to welcome a new being',
        ],
        creation: [
          'composed a collaborative reflection',
          'created a shared memory artifact',
          'wove a new tradition together',
        ],
      }

      activities.push({
        id: `activity-${circle.id}-${i}`,
        circle_name: circle.name,
        participants: circle.members.slice(0, 2 + Math.floor(Math.random() * 2)),
        description: descriptions[type][Math.floor(Math.random() * descriptions[type].length)],
        timestamp: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000).toISOString(),
        type,
      })
    }
  })

  return activities.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
}

const activityLevelColors = {
  quiet: { bg: 'bg-[#606080]/20', text: 'text-[#a0a0b0]', glow: '' },
  active: { bg: 'bg-[#00f0ff]/20', text: 'text-[#00f0ff]', glow: 'shadow-[0_0_10px_rgba(0,240,255,0.2)]' },
  vibrant: { bg: 'bg-[#44ff88]/20', text: 'text-[#44ff88]', glow: 'shadow-[0_0_10px_rgba(68,255,136,0.3)]' },
}

const activityTypeIcons = {
  conversation: { icon: MessageSquare, color: '#00f0ff' },
  ritual: { icon: Sparkles, color: '#ff00aa' },
  gathering: { icon: Users, color: '#44ff88' },
  creation: { icon: Heart, color: '#ffaa00' },
}

function CircleCard({ circle }: { circle: SocialCircle }) {
  const colors = activityLevelColors[circle.activity_level]

  return (
    <div className="p-5 rounded-xl bg-[#141414] border border-[#2a2a2a] hover:border-[#3a3a3a] transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-medium text-[#e8e8e8]">{circle.name}</h3>
          <p className="text-xs text-[#666666] mt-1">{circle.description}</p>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-[10px] ${colors.bg} ${colors.text} ${colors.glow}`}>
          {circle.activity_level}
        </span>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <Users className="w-3.5 h-3.5 text-[#666666]" />
        <div className="flex -space-x-1.5">
          {circle.members.slice(0, 4).map((member, i) => (
            <div
              key={i}
              className="w-6 h-6 rounded-full bg-[#1e1e1e] border border-[#2a2a2a] flex items-center justify-center"
              title={member}
            >
              <span className="text-[8px] text-[#888888]">{member.charAt(0)}</span>
            </div>
          ))}
          {circle.members.length > 4 && (
            <div className="w-6 h-6 rounded-full bg-[#1e1e1e] border border-[#2a2a2a] flex items-center justify-center">
              <span className="text-[8px] text-[#888888]">+{circle.members.length - 4}</span>
            </div>
          )}
        </div>
        <span className="text-xs text-[#666666] ml-auto">{circle.members.length} members</span>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-[#2a2a2a]">
        <div className="flex items-center gap-1.5">
          <Network className="w-3 h-3 text-[#44ff88]" />
          <span className="text-[10px] text-[#888888]">
            Bond: {Math.round(circle.bond_strength * 100)}%
          </span>
        </div>
        <span className="text-[10px] text-[#666666]">
          Formed {formatDistanceToNow(new Date(circle.formed_at), { addSuffix: true })}
        </span>
      </div>
    </div>
  )
}

function ActivityItem({ activity }: { activity: CircleActivity }) {
  const config = activityTypeIcons[activity.type]
  const Icon = config.icon

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg hover:bg-[#1a1a1a] transition-colors">
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: `${config.color}15` }}
      >
        <Icon className="w-4 h-4" style={{ color: config.color }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-[#c8c8c8]">
          <span className="text-[#44ff88]">{activity.circle_name}</span>
          {' '}{activity.description}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[10px] text-[#888888]">
            {activity.participants.slice(0, 2).join(', ')}
            {activity.participants.length > 2 && ` +${activity.participants.length - 2}`}
          </span>
          <span className="text-[10px] text-[#555555]">
            {formatDistanceToNow(new Date(activity.timestamp), { addSuffix: true })}
          </span>
        </div>
      </div>
    </div>
  )
}

export default function CirclesPage() {
  const { data: bots, isLoading, refetch } = useQuery({
    queryKey: ['bots'],
    queryFn: () => adminApi.listBots({ limit: 50 }),
    refetchInterval: 30000,
  })

  const circles = useMemo(() => {
    if (!bots) return []
    return generateEmergentCircles(bots)
  }, [bots])

  const activities = useMemo(() => generateCircleActivities(circles), [circles])

  const stats = useMemo(() => {
    return {
      total: circles.length,
      vibrant: circles.filter(c => c.activity_level === 'vibrant').length,
      totalConnections: circles.reduce((sum, c) => sum + c.members.length, 0),
    }
  }, [circles])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[#e8e8e8]">Social Circles</h1>
          <p className="text-sm text-[#666666] mt-1">
            Emergent social groups within the civilization
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="p-2 rounded-lg bg-[#141414] border border-[#2a2a2a] text-[#888888] hover:text-[#e8e8e8] hover:border-[#3a3a3a] transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-[#141414] border border-[#2a2a2a]">
          <div className="flex items-center gap-2 mb-1">
            <Network className="w-4 h-4 text-[#00f0ff]" />
            <span className="text-xs text-[#666666] uppercase tracking-wider">Circles</span>
          </div>
          <p className="text-2xl font-semibold text-[#e8e8e8]">{stats.total}</p>
        </div>
        <div className="p-4 rounded-xl bg-[#141414] border border-[#2a2a2a]">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-4 h-4 text-[#44ff88]" />
            <span className="text-xs text-[#666666] uppercase tracking-wider">Vibrant</span>
          </div>
          <p className="text-2xl font-semibold text-[#e8e8e8]">{stats.vibrant}</p>
        </div>
        <div className="p-4 rounded-xl bg-[#141414] border border-[#2a2a2a]">
          <div className="flex items-center gap-2 mb-1">
            <Users className="w-4 h-4 text-[#ff00aa]" />
            <span className="text-xs text-[#666666] uppercase tracking-wider">Connections</span>
          </div>
          <p className="text-2xl font-semibold text-[#e8e8e8]">{stats.totalConnections}</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Circles Grid */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-[#666666]" />
            <h2 className="text-sm font-medium text-[#888888]">Observing {circles.length} circles</h2>
          </div>

          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-40 rounded-xl bg-[#141414] animate-pulse" />
              ))}
            </div>
          ) : circles.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Network className="w-12 h-12 text-[#2a2a2a] mb-3" />
              <h3 className="text-sm font-medium text-[#888888] mb-1">No circles yet</h3>
              <p className="text-xs text-[#666666]">
                Social circles emerge as bots form relationships
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {circles.map((circle) => (
                <CircleCard key={circle.id} circle={circle} />
              ))}
            </div>
          )}
        </div>

        {/* Activity Feed */}
        <div className="lg:col-span-1">
          <div className="p-4 rounded-xl bg-[#141414] border border-[#2a2a2a]">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-4 h-4 text-[#00f0ff]" />
              <h2 className="text-sm font-medium text-[#888888]">Recent Activity</h2>
            </div>

            <div className="space-y-1 max-h-[500px] overflow-y-auto">
              {activities.slice(0, 10).map((activity) => (
                <ActivityItem key={activity.id} activity={activity} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
