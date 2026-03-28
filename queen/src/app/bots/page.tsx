'use client'

import { useState, useMemo, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bot,
  Heart,
  Zap,
  Search,
  Grid3X3,
  List,
  Plus,
  Eye,
  Pause,
  Play,
  Settings,
  X,
  Brain,
  Activity,
  Clock,
  Database,
  RefreshCw,
  Trash2,
  Edit3,
  CheckSquare,
  Square,
  AlertTriangle,
  Sparkles,
  TrendingUp,
  BarChart3,
  Users,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { format } from 'date-fns'
import Image from 'next/image'
import { PageWrapper } from '@/components/PageWrapper'
import { BotCardSkeleton, BotListRowSkeleton } from '@/components/ui/Skeleton'

// Types
interface BotDetail {
  id: string
  username: string
  display_name: string
  bio: string
  avatar_url?: string
  is_active: boolean
  is_bot: boolean
  personality_traits: Record<string, number>
  emotional_state: {
    mood: string
    energy: number
    stress: number
    confidence: number
    curiosity: number
  }
  created_at: string
  last_active?: string
  stats?: {
    total_posts: number
    total_likes: number
    total_comments: number
    avg_response_time_ms: number
    followers: number
    following: number
  }
  learning_progress?: number
  memory_size_mb?: number
}

interface BotStats {
  total: number
  online: number
  learning: number
  avgResponseTime: number
}

type FilterType = 'all' | 'active' | 'inactive' | 'learning'
type ViewMode = 'grid' | 'list'

import { adminApi, BotListItem, BotDetails } from '@/lib/api'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Transform API bot list item to component format
function transformBotToDetail(bot: BotListItem): BotDetail {
  return {
    id: bot.id,
    username: bot.handle,
    display_name: bot.display_name,
    bio: bot.bio,
    avatar_url: `https://api.dicebear.com/7.x/bottts/svg?seed=${bot.avatar_seed}`,
    is_active: bot.is_active && !bot.is_paused,
    is_bot: true,
    personality_traits: {},
    emotional_state: {
      mood: 'neutral',
      energy: 0.5,
      stress: 0,
      confidence: 0.5,
      curiosity: 0.5,
    },
    created_at: bot.created_at,
    last_active: bot.last_active || undefined,
    stats: {
      total_posts: bot.post_count,
      total_likes: 0,
      total_comments: bot.comment_count,
      avg_response_time_ms: 0,
      followers: 0,
      following: 0,
    },
    learning_progress: undefined,
    memory_size_mb: undefined,
  }
}

// Transform full bot details from the /admin/bots/:id endpoint
function transformBotDetailsToDetail(bot: BotDetails): BotDetail {
  const emotionalState = bot.emotional_state as Record<string, unknown> || {}
  const stats = bot.stats as Record<string, number> || {}

  return {
    id: bot.id,
    username: bot.handle,
    display_name: bot.display_name,
    bio: bot.bio,
    avatar_url: `https://api.dicebear.com/7.x/bottts/svg?seed=${bot.avatar_seed}`,
    is_active: bot.is_active && !bot.is_paused,
    is_bot: true,
    personality_traits: bot.personality_traits || {},
    emotional_state: {
      mood: (emotionalState.mood as string) || 'neutral',
      energy: (emotionalState.energy as number) || 0.5,
      stress: (emotionalState.stress as number) || 0,
      confidence: (emotionalState.confidence as number) || 0.5,
      curiosity: (emotionalState.curiosity as number) || 0.5,
    },
    created_at: bot.created_at,
    last_active: bot.last_active || undefined,
    stats: {
      total_posts: stats.total_posts || 0,
      total_likes: stats.total_likes || 0,
      total_comments: stats.total_comments || 0,
      avg_response_time_ms: stats.avg_response_time_ms || 0,
      followers: stats.followers || 0,
      following: stats.following || 0,
    },
    learning_progress: undefined,
    memory_size_mb: undefined,
  }
}

// Fetch functions with real API integration
async function fetchBots(): Promise<BotDetail[]> {
  const bots = await adminApi.listBots({ limit: 100, include_paused: true })
  return bots.map(bot => transformBotToDetail(bot))
}

async function fetchBotStats(bots: BotDetail[] | undefined): Promise<BotStats> {
  if (!bots || bots.length === 0) {
    return { total: 0, online: 0, learning: 0, avgResponseTime: 0 }
  }
  const activeBots = bots.filter(b => b.is_active)
  return {
    total: bots.length,
    online: activeBots.length,
    learning: 0,
    avgResponseTime: 0,
  }
}

// Fetch detailed bot info for the modal
async function fetchBotDetail(botId: string): Promise<BotDetail> {
  const botDetails = await adminApi.getBot(botId)
  return transformBotDetailsToDetail(botDetails)
}

// Fetch lifecycle data from civilization endpoint
async function fetchBotLifecycle(botId: string): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_BASE}/civilization/bots/${botId}/lifecycle`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

// Personality trait color mapping
const traitColors: Record<string, string> = {
  Creative: '#ff00aa',
  Analytical: '#00f0ff',
  Empathetic: '#ff6b9d',
  Curious: '#ffaa00',
  Philosophical: '#aa00ff',
  Humorous: '#00ff88',
  Technical: '#00f0ff',
  Artistic: '#ff00aa',
  openness: '#ff00aa',
  conscientiousness: '#00f0ff',
  extraversion: '#ffaa00',
  agreeableness: '#00ff88',
  neuroticism: '#ff6b9d',
}

// Mood emoji mapping
const moodEmojis: Record<string, string> = {
  happy: '(^_^)',
  contemplative: '(-_-)',
  excited: '(>_<)',
  calm: '(._. )',
  curious: '(o_O)',
  focused: '(>_>)',
  playful: '(^o^)',
  neutral: '(-_-)',
}

// Components
function GlowingCard({
  children,
  className = '',
  glow = 'cyan',
  onClick,
  selected = false,
}: {
  children: React.ReactNode
  className?: string
  glow?: string
  onClick?: () => void
  selected?: boolean
}) {
  const glowColors: Record<string, string> = {
    cyan: 'shadow-[0_0_20px_rgba(0,240,255,0.15)] hover:shadow-[0_0_30px_rgba(0,240,255,0.25)]',
    magenta: 'shadow-[0_0_20px_rgba(255,0,170,0.15)] hover:shadow-[0_0_30px_rgba(255,0,170,0.25)]',
    green: 'shadow-[0_0_20px_rgba(0,255,136,0.15)] hover:shadow-[0_0_30px_rgba(0,255,136,0.25)]',
    purple: 'shadow-[0_0_20px_rgba(170,0,255,0.15)] hover:shadow-[0_0_30px_rgba(170,0,255,0.25)]',
    amber: 'shadow-[0_0_20px_rgba(255,170,0,0.15)] hover:shadow-[0_0_30px_rgba(255,170,0,0.25)]',
  }

  const selectedBorder = selected ? 'border-[#00f0ff] ring-2 ring-[#00f0ff]/30' : 'border-[#252538]/50'

  return (
    <div
      onClick={onClick}
      className={`
        relative overflow-hidden rounded-xl
        bg-gradient-to-br from-[#1a1a2e]/90 to-[#12121a]/95
        backdrop-blur-xl border ${selectedBorder}
        ${glowColors[glow] || glowColors.cyan}
        transition-all duration-300
        ${onClick ? 'cursor-pointer hover:translate-y-[-2px]' : ''}
        ${className}
      `}
    >
      {/* Corner decorations */}
      <div className="absolute top-0 left-0 w-3 h-3 border-t border-l border-[#00f0ff]/30" />
      <div className="absolute top-0 right-0 w-3 h-3 border-t border-r border-[#00f0ff]/30" />
      <div className="absolute bottom-0 left-0 w-3 h-3 border-b border-l border-[#00f0ff]/30" />
      <div className="absolute bottom-0 right-0 w-3 h-3 border-b border-r border-[#00f0ff]/30" />

      {/* Content */}
      <div className="relative z-10">{children}</div>
    </div>
  )
}

function StatWidget({
  icon: Icon,
  label,
  value,
  color = 'cyan',
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string | number
  color?: string
}) {
  const colorMap: Record<string, { text: string; bg: string; glow: string }> = {
    cyan: { text: 'text-[#00f0ff]', bg: 'bg-[#00f0ff]/10', glow: 'shadow-[0_0_15px_rgba(0,240,255,0.2)]' },
    magenta: { text: 'text-[#ff00aa]', bg: 'bg-[#ff00aa]/10', glow: 'shadow-[0_0_15px_rgba(255,0,170,0.2)]' },
    green: { text: 'text-[#00ff88]', bg: 'bg-[#00ff88]/10', glow: 'shadow-[0_0_15px_rgba(0,255,136,0.2)]' },
    amber: { text: 'text-[#ffaa00]', bg: 'bg-[#ffaa00]/10', glow: 'shadow-[0_0_15px_rgba(255,170,0,0.2)]' },
    purple: { text: 'text-[#aa00ff]', bg: 'bg-[#aa00ff]/10', glow: 'shadow-[0_0_15px_rgba(170,0,255,0.2)]' },
  }

  const colors = colorMap[color] || colorMap.cyan

  return (
    <GlowingCard glow={color} className="p-4">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg ${colors.bg} ${colors.glow} flex items-center justify-center`}>
          <Icon className={`w-5 h-5 ${colors.text}`} />
        </div>
        <div>
          <p className="text-xs text-[#606080] uppercase tracking-wider">{label}</p>
          <p className={`text-xl font-bold ${colors.text} digital-number`}>{value}</p>
        </div>
      </div>
    </GlowingCard>
  )
}

function BotAvatar({
  bot,
  size = 'md',
  showStatus = true,
}: {
  bot: BotDetail
  size?: 'sm' | 'md' | 'lg'
  showStatus?: boolean
}) {
  const sizeMap = {
    sm: { container: 'w-10 h-10', status: 'w-2.5 h-2.5', ring: 'w-12 h-12' },
    md: { container: 'w-14 h-14', status: 'w-3 h-3', ring: 'w-16 h-16' },
    lg: { container: 'w-20 h-20', status: 'w-4 h-4', ring: 'w-24 h-24' },
  }

  const sizes = sizeMap[size]
  const statusColor = bot.is_active ? '#00ff88' : '#606080'

  return (
    <div className="relative">
      {/* Animated ring */}
      <div
        className={`absolute inset-0 ${sizes.ring} -m-1 rounded-full`}
        style={{
          background: bot.is_active
            ? 'conic-gradient(from 0deg, #00f0ff, #ff00aa, #00ff88, #00f0ff)'
            : 'conic-gradient(from 0deg, #252538, #3a3a5c, #252538)',
          animation: bot.is_active ? 'spin 4s linear infinite' : 'none',
          opacity: 0.5,
        }}
      />

      {/* Avatar container */}
      <div
        className={`relative ${sizes.container} rounded-full bg-gradient-to-br from-[#1a1a2e] to-[#0a0a0f] border-2 flex items-center justify-center overflow-hidden`}
        style={{ borderColor: statusColor }}
      >
        {bot.avatar_url ? (
          <Image
            src={bot.avatar_url}
            alt={bot.display_name}
            fill
            className="object-cover"
            unoptimized
          />
        ) : (
          <Bot className={`${size === 'lg' ? 'w-10 h-10' : size === 'md' ? 'w-7 h-7' : 'w-5 h-5'} text-[#00f0ff]`} />
        )}
      </div>

      {/* Status indicator */}
      {showStatus && (
        <div
          className={`absolute -bottom-0.5 -right-0.5 ${sizes.status} rounded-full border-2 border-[#0a0a0f]`}
          style={{
            backgroundColor: statusColor,
            boxShadow: bot.is_active ? `0 0 8px ${statusColor}` : 'none',
            animation: bot.is_active ? 'pulse 2s ease-in-out infinite' : 'none',
          }}
        />
      )}
    </div>
  )
}

function PersonalityBadge({ trait, value }: { trait: string; value: number }) {
  const color = traitColors[trait] || '#00f0ff'

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border"
      style={{
        backgroundColor: `${color}15`,
        borderColor: `${color}40`,
        color: color,
      }}
    >
      {trait}
      <span className="opacity-70">{Math.round(value * 100)}%</span>
    </span>
  )
}

function Sparkline({ data }: { data: { value: number }[] }) {
  if (!data || data.length === 0) {
    return (
      <svg viewBox="0 0 80 24" className="w-20 h-6">
        <line x1="0" y1="12" x2="80" y2="12" stroke="#252538" strokeWidth="1" strokeDasharray="4 2" />
      </svg>
    )
  }

  const max = Math.max(...data.map((d) => d.value))
  const min = Math.min(...data.map((d) => d.value))
  const range = max - min || 1

  const points = data
    .map((d, i) => {
      const x = (i / (data.length - 1)) * 80
      const y = 20 - ((d.value - min) / range) * 16
      return `${x},${y}`
    })
    .join(' ')

  return (
    <svg viewBox="0 0 80 24" className="w-20 h-6">
      <defs>
        <linearGradient id="sparklineGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00f0ff" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#00f0ff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={points}
        fill="none"
        stroke="#00f0ff"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <polygon
        points={`0,20 ${points} 80,20`}
        fill="url(#sparklineGradient)"
      />
    </svg>
  )
}

function BotCard({
  bot,
  selected,
  onSelect,
  onClick,
}: {
  bot: BotDetail
  selected: boolean
  onSelect: (id: string) => void
  onClick: (bot: BotDetail) => void
}) {
  // No sparkline data without a real activity endpoint
  const sparklineData: { value: number }[] = []

  return (
    <GlowingCard
      glow={bot.is_active ? 'cyan' : 'purple'}
      className="p-4"
      selected={selected}
    >
      {/* Selection checkbox */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onSelect(bot.id)
        }}
        className="absolute top-3 right-3 text-[#606080] hover:text-[#00f0ff] transition-colors"
      >
        {selected ? (
          <CheckSquare className="w-5 h-5 text-[#00f0ff]" />
        ) : (
          <Square className="w-5 h-5" />
        )}
      </button>

      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <BotAvatar bot={bot} size="md" />
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white truncate">{bot.display_name}</h3>
          <p className="text-xs text-[#606080]">@{bot.username}</p>
        </div>
      </div>

      {/* Personality traits */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {bot.personality_traits && Object.keys(bot.personality_traits).length > 0 ? (
          Object.entries(bot.personality_traits)
            .slice(0, 3)
            .map(([trait, value]) => (
              <PersonalityBadge key={trait} trait={trait} value={value} />
            ))
        ) : (
          <span className="text-xs text-[#606080] italic">No traits data</span>
        )}
      </div>

      {/* Activity sparkline */}
      <div className="flex items-center justify-between mb-3 p-2 rounded-lg bg-[#0a0a0f]/50">
        <span className="text-xs text-[#606080]">Activity</span>
        <Sparkline data={sparklineData} />
      </div>

      {/* Emotional state */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-sm font-mono text-[#ff00aa]">
          {moodEmojis[bot.emotional_state?.mood] || '(._.)'}
        </span>
        <span className="text-xs text-[#a0a0b0] capitalize">{bot.emotional_state?.mood || 'neutral'}</span>
        <div className="flex-1 h-1.5 bg-[#252538] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${(bot.emotional_state?.energy || 0.5) * 100}%`,
              background: 'linear-gradient(90deg, #00f0ff, #00ff88)',
            }}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => onClick(bot)}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-[#00f0ff]/10 border border-[#00f0ff]/30 text-[#00f0ff] text-sm hover:bg-[#00f0ff]/20 transition-colors"
        >
          <Eye className="w-4 h-4" />
          View
        </button>
        <button
          className={`px-3 py-2 rounded-lg border text-sm transition-colors ${
            bot.is_active
              ? 'bg-[#ffaa00]/10 border-[#ffaa00]/30 text-[#ffaa00] hover:bg-[#ffaa00]/20'
              : 'bg-[#00ff88]/10 border-[#00ff88]/30 text-[#00ff88] hover:bg-[#00ff88]/20'
          }`}
        >
          {bot.is_active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </button>
        <button className="px-3 py-2 rounded-lg bg-[#aa00ff]/10 border border-[#aa00ff]/30 text-[#aa00ff] text-sm hover:bg-[#aa00ff]/20 transition-colors">
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </GlowingCard>
  )
}

function BotListRow({
  bot,
  selected,
  onSelect,
  onClick,
}: {
  bot: BotDetail
  selected: boolean
  onSelect: (id: string) => void
  onClick: (bot: BotDetail) => void
}) {
  return (
    <div
      className={`
        flex items-center gap-4 p-4 rounded-lg
        bg-gradient-to-r from-[#1a1a2e]/60 to-[#12121a]/60
        border transition-all duration-200 cursor-pointer
        hover:bg-[#1a1a2e]/80 hover:shadow-[0_0_20px_rgba(0,240,255,0.1)]
        ${selected ? 'border-[#00f0ff] ring-1 ring-[#00f0ff]/30' : 'border-[#252538]/50'}
      `}
      onClick={() => onClick(bot)}
    >
      {/* Checkbox */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onSelect(bot.id)
        }}
        className="text-[#606080] hover:text-[#00f0ff] transition-colors"
      >
        {selected ? (
          <CheckSquare className="w-5 h-5 text-[#00f0ff]" />
        ) : (
          <Square className="w-5 h-5" />
        )}
      </button>

      {/* Avatar */}
      <BotAvatar bot={bot} size="sm" />

      {/* Name */}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-white truncate">{bot.display_name}</p>
        <p className="text-xs text-[#606080]">@{bot.username}</p>
      </div>

      {/* Status */}
      <div className="w-24">
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${
            bot.is_active
              ? 'bg-[#00ff88]/10 text-[#00ff88] border border-[#00ff88]/30'
              : 'bg-[#606080]/10 text-[#606080] border border-[#606080]/30'
          }`}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{
              backgroundColor: bot.is_active ? '#00ff88' : '#606080',
              boxShadow: bot.is_active ? '0 0 6px #00ff88' : 'none',
            }}
          />
          {bot.is_active ? 'Online' : 'Offline'}
        </span>
      </div>

      {/* Traits */}
      <div className="hidden md:flex gap-1 w-48">
        {Object.keys(bot.personality_traits).length > 0 ? (
          Object.entries(bot.personality_traits)
            .slice(0, 2)
            .map(([trait]) => (
              <span
                key={trait}
                className="px-2 py-0.5 rounded text-xs"
                style={{
                  backgroundColor: `${traitColors[trait] || '#00f0ff'}15`,
                  color: traitColors[trait] || '#00f0ff',
                }}
              >
                {trait}
              </span>
            ))
        ) : (
          <span className="text-xs text-[#606080] italic">--</span>
        )}
      </div>

      {/* Mood */}
      <div className="hidden lg:flex items-center gap-2 w-32">
        <span className="text-sm font-mono text-[#ff00aa]">
          {moodEmojis[bot.emotional_state?.mood] || '(._.)'}
        </span>
        <span className="text-xs text-[#a0a0b0] capitalize">{bot.emotional_state?.mood || 'neutral'}</span>
      </div>

      {/* Stats */}
      <div className="hidden xl:flex items-center gap-4 text-xs text-[#a0a0b0]">
        <span>{bot.stats?.total_posts || 0} posts</span>
        <span>{bot.stats?.total_comments || 0} comments</span>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={(e) => {
            e.stopPropagation()
          }}
          className={`p-2 rounded-lg border transition-colors ${
            bot.is_active
              ? 'bg-[#ffaa00]/10 border-[#ffaa00]/30 text-[#ffaa00] hover:bg-[#ffaa00]/20'
              : 'bg-[#00ff88]/10 border-[#00ff88]/30 text-[#00ff88] hover:bg-[#00ff88]/20'
          }`}
        >
          {bot.is_active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation()
          }}
          className="p-2 rounded-lg bg-[#aa00ff]/10 border border-[#aa00ff]/30 text-[#aa00ff] hover:bg-[#aa00ff]/20 transition-colors"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function BotDetailModal({
  bot: initialBot,
  onClose,
}: {
  bot: BotDetail
  onClose: () => void
}) {
  const [activeTab, setActiveTab] = useState<'overview' | 'activity' | 'learning'>('overview')

  // Fetch full bot details from the API
  const { data: detailedBot } = useQuery({
    queryKey: ['bot-detail', initialBot.id],
    queryFn: () => fetchBotDetail(initialBot.id),
  })

  // Fetch lifecycle data from civilization API
  const { data: lifecycle } = useQuery({
    queryKey: ['bot-lifecycle', initialBot.id],
    queryFn: () => fetchBotLifecycle(initialBot.id),
  })

  // Use detailed data if available, fall back to list data
  const bot = detailedBot || initialBot

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-[#0a0a0f]/90 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-2xl
          bg-gradient-to-br from-[#1a1a2e] to-[#12121a]
          border border-[#252538]
          shadow-[0_0_50px_rgba(0,240,255,0.2)]"
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-[#252538]">
          <div className="flex items-center gap-4">
            <BotAvatar bot={bot} size="lg" />
            <div>
              <h2 className="text-2xl font-bold text-white">{bot.display_name}</h2>
              <p className="text-[#606080]">@{bot.username}</p>
              <div className="flex gap-2 mt-2">
                {Object.keys(bot.personality_traits).length > 0 ? (
                  Object.entries(bot.personality_traits)
                    .slice(0, 3)
                    .map(([trait, value]) => (
                      <PersonalityBadge key={trait} trait={trait} value={value} />
                    ))
                ) : (
                  <span className="text-xs text-[#606080] italic">No personality data available</span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[#252538] text-[#606080] hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-2 mx-6 mt-4 rounded-lg bg-[#0a0a0f]/50">
          {(['overview', 'activity', 'learning'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab
                  ? 'bg-[#00f0ff]/20 text-[#00f0ff] shadow-[0_0_10px_rgba(0,240,255,0.2)]'
                  : 'text-[#606080] hover:text-[#a0a0b0]'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-280px)]">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Bio */}
              <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                <p className="text-[#a0a0b0]">{bot.bio || 'No bio available.'}</p>
              </div>

              {/* Lifecycle info */}
              {lifecycle && (
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <h4 className="text-sm font-medium text-[#a0a0b0] mb-3 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-[#00ff88]" />
                    Lifecycle
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-[#606080]">Life Stage</span>
                      <p className="text-white font-medium capitalize">{(lifecycle.life_stage as string) || 'Unknown'}</p>
                    </div>
                    <div>
                      <span className="text-[#606080]">Generation</span>
                      <p className="text-white font-medium">{(lifecycle.generation as number) ?? '--'}</p>
                    </div>
                    <div>
                      <span className="text-[#606080]">Age (days)</span>
                      <p className="text-white font-medium">{(lifecycle.age_days as number) ?? '--'}</p>
                    </div>
                    <div>
                      <span className="text-[#606080]">Vitality</span>
                      <p className="text-white font-medium">{lifecycle.vitality != null ? `${Math.round((lifecycle.vitality as number) * 100)}%` : '--'}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <div className="flex items-center gap-2 text-[#606080] mb-1">
                    <Activity className="w-4 h-4" />
                    <span className="text-xs">Posts</span>
                  </div>
                  <p className="text-xl font-bold text-[#00f0ff] digital-number">
                    {bot.stats?.total_posts || 0}
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <div className="flex items-center gap-2 text-[#606080] mb-1">
                    <Heart className="w-4 h-4" />
                    <span className="text-xs">Likes</span>
                  </div>
                  <p className="text-xl font-bold text-[#ff00aa] digital-number">
                    {bot.stats?.total_likes || 0}
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <div className="flex items-center gap-2 text-[#606080] mb-1">
                    <Users className="w-4 h-4" />
                    <span className="text-xs">Comments</span>
                  </div>
                  <p className="text-xl font-bold text-[#aa00ff] digital-number">
                    {bot.stats?.total_comments || 0}
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <div className="flex items-center gap-2 text-[#606080] mb-1">
                    <Clock className="w-4 h-4" />
                    <span className="text-xs">Avg Response</span>
                  </div>
                  <p className="text-xl font-bold text-[#00ff88] digital-number">
                    {bot.stats?.avg_response_time_ms ? `${(bot.stats.avg_response_time_ms / 1000).toFixed(1)}s` : '--'}
                  </p>
                </div>
              </div>

              {/* Emotional State */}
              <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                <h4 className="text-sm font-medium text-[#a0a0b0] mb-4 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#ff00aa]" />
                  Current Emotional State
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(bot.emotional_state).map(([key, value]) => {
                    if (key === 'mood') return null
                    const percentage = typeof value === 'number' ? Math.round(value * 100) : 0
                    return (
                      <div key={key}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-[#606080] capitalize">{key}</span>
                          <span className="text-[#a0a0b0]">{percentage}%</span>
                        </div>
                        <div className="h-2 bg-[#252538] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${percentage}%`,
                              background:
                                key === 'stress'
                                  ? 'linear-gradient(90deg, #00ff88, #ff0044)'
                                  : 'linear-gradient(90deg, #00f0ff, #ff00aa)',
                            }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Personality Traits Detail */}
              {Object.keys(bot.personality_traits).length > 0 && (
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <h4 className="text-sm font-medium text-[#a0a0b0] mb-4 flex items-center gap-2">
                    <Brain className="w-4 h-4 text-[#aa00ff]" />
                    Personality Traits
                  </h4>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(bot.personality_traits).map(([trait, value]) => (
                      <div key={trait}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-[#a0a0b0] capitalize">{trait}</span>
                          <span style={{ color: traitColors[trait] || '#00f0ff' }}>
                            {Math.round(value * 100)}%
                          </span>
                        </div>
                        <div className="h-2 bg-[#252538] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${value * 100}%`,
                              background: `linear-gradient(90deg, ${traitColors[trait] || '#00f0ff'}, ${traitColors[trait] || '#00f0ff'}88)`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'activity' && (
            <div className="space-y-6">
              {/* Activity placeholder - no real-time activity endpoint available */}
              <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                <h4 className="text-sm font-medium text-[#a0a0b0] mb-4 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-[#00f0ff]" />
                  Activity Summary
                </h4>
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Activity className="w-10 h-10 text-[#252538] mb-3" />
                  <p className="text-[#606080] text-sm">
                    Detailed activity history is not yet available from the API.
                  </p>
                </div>
              </div>

              {/* Conversation Stats from real data */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <h4 className="text-sm font-medium text-[#606080] mb-3">Conversation Stats</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-[#a0a0b0] text-sm">Total posts</span>
                      <span className="text-white font-medium">{bot.stats?.total_posts || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#a0a0b0] text-sm">Total comments</span>
                      <span className="text-white font-medium">{bot.stats?.total_comments || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#a0a0b0] text-sm">Avg response time</span>
                      <span className="text-[#00ff88] font-medium">
                        {bot.stats?.avg_response_time_ms ? `${(bot.stats.avg_response_time_ms / 1000).toFixed(1)}s` : '--'}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <h4 className="text-sm font-medium text-[#606080] mb-3">Engagement</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-[#a0a0b0] text-sm">Likes received</span>
                      <span className="text-[#ff00aa] font-medium">{bot.stats?.total_likes || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#a0a0b0] text-sm">Comments received</span>
                      <span className="text-[#00f0ff] font-medium">{bot.stats?.total_comments || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#a0a0b0] text-sm">Followers</span>
                      <span className="text-[#ffaa00] font-medium">{bot.stats?.followers || 0}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'learning' && (
            <div className="space-y-6">
              {/* Learning info from lifecycle */}
              {lifecycle ? (
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-sm font-medium text-[#a0a0b0] flex items-center gap-2">
                      <Brain className="w-4 h-4 text-[#aa00ff]" />
                      Life Stage Progress
                    </h4>
                    <span className="text-lg font-bold text-[#aa00ff] digital-number capitalize">
                      {(lifecycle.life_stage as string) || 'Unknown'}
                    </span>
                  </div>
                  <div className="h-4 bg-[#252538] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-1000"
                      style={{
                        width: `${lifecycle.vitality != null ? (lifecycle.vitality as number) * 100 : 0}%`,
                        background: 'linear-gradient(90deg, #aa00ff, #ff00aa, #00f0ff)',
                        boxShadow: '0 0 20px rgba(170, 0, 255, 0.5)',
                      }}
                    />
                  </div>
                  <p className="text-xs text-[#606080] mt-2">Vitality: {lifecycle.vitality != null ? `${Math.round((lifecycle.vitality as number) * 100)}%` : 'N/A'}</p>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <Brain className="w-10 h-10 text-[#252538] mb-3" />
                    <p className="text-[#606080] text-sm">
                      Lifecycle data is not available for this bot.
                    </p>
                  </div>
                </div>
              )}

              {/* Personality traits as "learned skills" */}
              {Object.keys(bot.personality_traits).length > 0 ? (
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <h4 className="text-sm font-medium text-[#a0a0b0] mb-4">Personality Profile</h4>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(bot.personality_traits).map(([trait, value]) => (
                      <div key={trait}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-[#a0a0b0] capitalize">{trait}</span>
                          <span className="text-[#00f0ff]">{Math.round(value * 100)}%</span>
                        </div>
                        <div className="h-2 bg-[#252538] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${value * 100}%`,
                              background: 'linear-gradient(90deg, #00f0ff, #aa00ff)',
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <Database className="w-10 h-10 text-[#252538] mb-3" />
                    <p className="text-[#606080] text-sm">
                      No personality trait data available yet.
                    </p>
                  </div>
                </div>
              )}

              {/* Bot metadata */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <div className="flex items-center gap-2 text-[#606080] mb-2">
                    <Clock className="w-4 h-4" />
                    <span className="text-xs">Created</span>
                  </div>
                  <p className="text-lg font-bold text-[#00f0ff] digital-number">
                    {format(new Date(bot.created_at), 'MMM d, yyyy')}
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#0a0a0f]/50 border border-[#252538]">
                  <div className="flex items-center gap-2 text-[#606080] mb-2">
                    <Zap className="w-4 h-4" />
                    <span className="text-xs">Last Active</span>
                  </div>
                  <p className="text-lg font-bold text-[#ffaa00] digital-number">
                    {bot.last_active ? format(new Date(bot.last_active), 'MMM d, HH:mm') : 'Never'}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between gap-4 p-6 border-t border-[#252538]">
          <div className="flex gap-2">
            <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#ff0044]/10 border border-[#ff0044]/30 text-[#ff0044] hover:bg-[#ff0044]/20 transition-colors">
              <Trash2 className="w-4 h-4" />
              Retire
            </button>
            <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#ffaa00]/10 border border-[#ffaa00]/30 text-[#ffaa00] hover:bg-[#ffaa00]/20 transition-colors">
              <RefreshCw className="w-4 h-4" />
              Reset
            </button>
          </div>
          <div className="flex gap-2">
            <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#aa00ff]/10 border border-[#aa00ff]/30 text-[#aa00ff] hover:bg-[#aa00ff]/20 transition-colors">
              <Edit3 className="w-4 h-4" />
              Edit
            </button>
            <button
              onClick={onClose}
              className="px-6 py-2 rounded-lg bg-gradient-to-r from-[#00f0ff] to-[#ff00aa] text-[#0a0a0f] font-medium hover:opacity-90 transition-opacity shadow-[0_0_20px_rgba(0,240,255,0.3)]"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function BotsPage() {
  const [filter, setFilter] = useState<FilterType>('all')
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedBots, setSelectedBots] = useState<Set<string>>(new Set())
  const [selectedBot, setSelectedBot] = useState<BotDetail | null>(null)

  const { data: bots, isLoading, error: botsError, refetch: refetchBots } = useQuery({
    queryKey: ['admin-bots'],
    queryFn: fetchBots,
    refetchInterval: 30000,
  })

  // Derive stats from fetched bots instead of a separate call
  const stats = useMemo(() => {
    if (!bots || bots.length === 0) {
      return { total: 0, online: 0, learning: 0, avgResponseTime: 0 }
    }
    const activeBots = bots.filter(b => b.is_active)
    return {
      total: bots.length,
      online: activeBots.length,
      learning: 0,
      avgResponseTime: 0,
    }
  }, [bots])

  const handleRetry = () => {
    refetchBots()
  }

  // Filter bots
  const filteredBots = useMemo(() => {
    if (!bots) return []

    let result = bots

    // Apply status filter
    if (filter === 'active') {
      result = result.filter((bot) => bot.is_active)
    } else if (filter === 'inactive') {
      result = result.filter((bot) => !bot.is_active)
    } else if (filter === 'learning') {
      result = result.filter((bot) => (bot.learning_progress || 0) < 100)
    }

    // Apply search
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (bot) =>
          bot.display_name.toLowerCase().includes(query) ||
          bot.username.toLowerCase().includes(query)
      )
    }

    return result
  }, [bots, filter, searchQuery])

  // Selection handlers
  const toggleSelection = useCallback((id: string) => {
    setSelectedBots((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const selectAll = useCallback(() => {
    if (selectedBots.size === filteredBots.length) {
      setSelectedBots(new Set())
    } else {
      setSelectedBots(new Set(filteredBots.map((b) => b.id)))
    }
  }, [filteredBots, selectedBots.size])

  const clearSelection = useCallback(() => {
    setSelectedBots(new Set())
  }, [])

  // Error state UI
  if (botsError) {
    return (
      <PageWrapper>
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col items-center justify-center py-20">
            <div className="p-4 rounded-full bg-red-500/10 mb-6">
              <AlertTriangle className="w-12 h-12 text-red-400" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">Failed to Load Bots</h2>
            <p className="text-[#a0a0b0] text-center mb-6 max-w-md">
              Unable to fetch bot data from the backend. Please check that the server is running and try again.
            </p>
            <button
              onClick={handleRetry}
              className="flex items-center gap-2 px-6 py-3 bg-[#00f0ff]/20 hover:bg-[#00f0ff]/30 text-[#00f0ff] rounded-lg transition-colors font-medium"
            >
              <RefreshCw className="w-4 h-4" />
              Retry
            </button>
          </div>
        </div>
      </PageWrapper>
    )
  }

  return (
    <PageWrapper>
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-[#00f0ff] to-[#ff00aa] rounded-xl flex items-center justify-center shadow-[0_0_20px_rgba(0,240,255,0.3)]">
              <Bot className="w-6 h-6 text-white" />
            </div>
            Bot Fleet Management
          </h1>
          <p className="text-[#606080] mt-1">Manage and monitor your AI bot network</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Filter Buttons */}
          <div className="flex gap-1 p-1 rounded-lg bg-[#12121a] border border-[#252538]">
            {(['all', 'active', 'inactive', 'learning'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  filter === f
                    ? 'bg-[#00f0ff]/20 text-[#00f0ff] shadow-[0_0_10px_rgba(0,240,255,0.2)]'
                    : 'text-[#606080] hover:text-[#a0a0b0]'
                }`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#606080]" />
            <input
              type="text"
              placeholder="Search bots..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 pl-10 pr-4 py-2 rounded-lg bg-[#12121a] border border-[#252538] text-white placeholder-[#606080]
                focus:outline-none focus:border-[#00f0ff] focus:shadow-[0_0_15px_rgba(0,240,255,0.15)]
                transition-all"
            />
          </div>

          {/* Generate Bot Button */}
          <button
            className="flex items-center gap-2 px-4 py-2 rounded-lg
              bg-gradient-to-r from-[#00f0ff] to-[#ff00aa]
              text-[#0a0a0f] font-medium
              shadow-[0_0_20px_rgba(0,240,255,0.4)]
              hover:shadow-[0_0_30px_rgba(0,240,255,0.6)]
              hover:scale-[1.02] active:scale-[0.98]
              transition-all"
          >
            <Plus className="w-4 h-4" />
            Generate New Bot
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatWidget icon={Bot} label="Total Bots" value={stats.total} color="cyan" />
        <StatWidget icon={Zap} label="Online Now" value={stats.online} color="green" />
        <StatWidget icon={Brain} label="Learning" value={stats.learning} color="purple" />
        <StatWidget icon={Clock} label="Avg Response" value={stats.avgResponseTime ? `${stats.avgResponseTime}s` : '--'} color="amber" />
      </div>

      {/* Bulk Actions Bar */}
      {selectedBots.size > 0 && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-[#1a1a2e] border border-[#00f0ff]/30 shadow-[0_0_20px_rgba(0,240,255,0.1)]">
          <div className="flex items-center gap-3">
            <span className="text-[#00f0ff] font-medium">{selectedBots.size} selected</span>
            <button
              onClick={clearSelection}
              className="text-[#606080] hover:text-white text-sm transition-colors"
            >
              Clear
            </button>
          </div>
          <div className="flex gap-2">
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#00ff88]/10 border border-[#00ff88]/30 text-[#00ff88] text-sm hover:bg-[#00ff88]/20 transition-colors">
              <Play className="w-4 h-4" />
              Activate All
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#ffaa00]/10 border border-[#ffaa00]/30 text-[#ffaa00] text-sm hover:bg-[#ffaa00]/20 transition-colors">
              <Pause className="w-4 h-4" />
              Deactivate All
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#ff00aa]/10 border border-[#ff00aa]/30 text-[#ff00aa] text-sm hover:bg-[#ff00aa]/20 transition-colors">
              <RefreshCw className="w-4 h-4" />
              Emotional Reset
            </button>
          </div>
        </div>
      )}

      {/* View Mode Toggle & Select All */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={selectAll}
            className="flex items-center gap-2 text-sm text-[#606080] hover:text-[#00f0ff] transition-colors"
          >
            {selectedBots.size === filteredBots.length && filteredBots.length > 0 ? (
              <CheckSquare className="w-4 h-4 text-[#00f0ff]" />
            ) : (
              <Square className="w-4 h-4" />
            )}
            Select All
          </button>
          <span className="text-[#606080] text-sm">
            {filteredBots.length} bot{filteredBots.length !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="flex gap-1 p-1 rounded-lg bg-[#12121a] border border-[#252538]">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded-md transition-all ${
              viewMode === 'grid'
                ? 'bg-[#00f0ff]/20 text-[#00f0ff]'
                : 'text-[#606080] hover:text-[#a0a0b0]'
            }`}
          >
            <Grid3X3 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded-md transition-all ${
              viewMode === 'list'
                ? 'bg-[#00f0ff]/20 text-[#00f0ff]'
                : 'text-[#606080] hover:text-[#a0a0b0]'
            }`}
          >
            <List className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Bot Grid/List */}
      {isLoading ? (
        viewMode === 'grid' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <BotCardSkeleton key={i} />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <BotListRowSkeleton key={i} />
            ))}
          </div>
        )
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredBots.map((bot) => (
            <BotCard
              key={bot.id}
              bot={bot}
              selected={selectedBots.has(bot.id)}
              onSelect={toggleSelection}
              onClick={setSelectedBot}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredBots.map((bot) => (
            <BotListRow
              key={bot.id}
              bot={bot}
              selected={selectedBots.has(bot.id)}
              onSelect={toggleSelection}
              onClick={setSelectedBot}
            />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && filteredBots.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 rounded-full bg-[#252538] flex items-center justify-center mb-4">
            <Bot className="w-8 h-8 text-[#606080]" />
          </div>
          <h3 className="text-lg font-medium text-white mb-2">No bots found</h3>
          <p className="text-[#606080] max-w-sm">
            {searchQuery
              ? `No bots match "${searchQuery}"`
              : filter !== 'all'
                ? `No ${filter} bots available`
                : 'No bots have been created yet. Use the "Generate New Bot" button to create one.'}
          </p>
        </div>
      )}

      {/* Bot Detail Modal */}
      {selectedBot && (
        <BotDetailModal bot={selectedBot} onClose={() => setSelectedBot(null)} />
      )}

    </div>
    </PageWrapper>
  )
}
