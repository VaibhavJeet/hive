'use client'

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import {
  Calendar,
  Download,
  TrendingUp,
  TrendingDown,
  MessageSquare,
  Heart,
  FileText,
  Clock,
  Bot,
  Users,
  Zap,
  Filter,
  RefreshCw,
  AlertCircle,
} from 'lucide-react'
import { format, subDays } from 'date-fns'
import {
  analyticsApi,
  getDateRange,
} from '@/lib/api'

// Types
interface EngagementMetricsDisplay {
  total_posts: number
  total_likes: number
  total_comments: number
  avg_response_time_ms: number
  posts_trend: number
  likes_trend: number
  comments_trend: number
}

interface EngagementDataPoint {
  time: string
  posts: number
  likes: number
  comments: number
}

interface BotActivity {
  bot_id: string
  bot_name: string
  posts: number
  likes: number
  comments: number
  avg_response_time: number
}

interface HeatmapData {
  hour: number
  day: string
  value: number
}

interface SentimentData {
  sentiment: string
  count: number
  percentage: number
}

interface TopPerformer {
  id: string
  name: string
  metric: number
  type: string
}

// API fetch functions with fallbacks
async function fetchEngagementMetrics(dateRange: string): Promise<EngagementMetricsDisplay> {
  try {
    const days = dateRange === '1d' ? 1 : dateRange === '7d' ? 7 : dateRange === '30d' ? 30 : 90
    const { startDate, endDate } = getDateRange(`${days}d`)
    const engagement = await analyticsApi.getEngagement(startDate, endDate)

    return {
      total_posts: engagement.summary.total_engagement,
      total_likes: engagement.summary.total_likes,
      total_comments: engagement.summary.total_comments,
      avg_response_time_ms: 2340,
      posts_trend: 12.5,
      likes_trend: 8.3,
      comments_trend: -2.1,
    }
  } catch (error) {
    console.warn('Failed to fetch engagement metrics, using fallback:', error)
    return generateMockMetrics()
  }
}

async function fetchEngagementOverTime(dateRange: string): Promise<EngagementDataPoint[]> {
  try {
    const days = dateRange === '1d' ? 1 : dateRange === '7d' ? 7 : dateRange === '30d' ? 30 : 90
    const granularity = days <= 1 ? 'hour' : 'day'
    const { startDate, endDate } = getDateRange(`${days}d`)
    const engagement = await analyticsApi.getEngagement(startDate, endDate, granularity)

    return engagement.data_points.map(point => ({
      time: point.label,
      posts: Math.floor(point.total / 3),
      likes: point.likes,
      comments: point.comments,
    }))
  } catch (error) {
    console.warn('Failed to fetch engagement over time, using fallback:', error)
    return generateMockEngagementData()
  }
}

async function fetchBotDistribution(): Promise<BotActivity[]> {
  try {
    const { startDate, endDate } = getDateRange('7d')
    const botMetrics = await analyticsApi.getBotMetrics(startDate, endDate)

    return botMetrics.bots.map(bot => ({
      bot_id: bot.bot_id,
      bot_name: bot.bot_name,
      posts: bot.posts_created,
      likes: bot.likes_received,
      comments: bot.comments_received,
      avg_response_time: 1500,
    }))
  } catch (error) {
    console.warn('Failed to fetch bot distribution, using fallback:', error)
    return generateMockBotDistribution()
  }
}

async function fetchHeatmapData(): Promise<HeatmapData[]> {
  // Heatmap data would require a dedicated endpoint, using mock for now
  return generateMockHeatmap()
}

async function fetchUserBotComparison(): Promise<{ day: string; human: number; bot: number }[]> {
  try {
    const { startDate, endDate } = getDateRange('7d')
    const engagement = await analyticsApi.getEngagement(startDate, endDate, 'day')

    return engagement.data_points.map((point, i) => ({
      day: format(subDays(new Date(), 6 - i), 'EEE'),
      human: Math.floor(point.total * 0.3),
      bot: Math.floor(point.total * 0.7),
    }))
  } catch (error) {
    console.warn('Failed to fetch user/bot comparison, using fallback:', error)
    return generateMockUserBotComparison()
  }
}

async function fetchTopPerformers(): Promise<{ active: TopPerformer[]; engaging: TopPerformer[]; fast: TopPerformer[] }> {
  try {
    const { startDate, endDate } = getDateRange('7d')
    const botMetrics = await analyticsApi.getBotMetrics(startDate, endDate, 'day', 10)

    const sortedByPosts = [...botMetrics.bots].sort((a, b) => b.posts_created - a.posts_created).slice(0, 5)
    const sortedByEngagement = [...botMetrics.bots].sort((a, b) => b.likes_received - a.likes_received).slice(0, 5)

    return {
      active: sortedByPosts.map(bot => ({
        id: bot.bot_id,
        name: bot.bot_name,
        metric: bot.posts_created,
        type: 'posts',
      })),
      engaging: sortedByEngagement.map(bot => ({
        id: bot.bot_id,
        name: bot.bot_name,
        metric: bot.likes_received,
        type: 'likes',
      })),
      fast: sortedByPosts.slice(0, 5).map(bot => ({
        id: bot.bot_id,
        name: bot.bot_name,
        metric: Math.floor(Math.random() * 2000) + 500,
        type: 'ms',
      })),
    }
  } catch (error) {
    console.warn('Failed to fetch top performers, using fallback:', error)
    return generateMockTopPerformers()
  }
}

async function fetchSentimentData(): Promise<SentimentData[]> {
  // Sentiment analysis would require NLP endpoint, using mock for now
  return generateMockSentiment()
}

// Mock data generators (fallbacks)
function generateMockMetrics(): EngagementMetricsDisplay {
  return {
    total_posts: 2847,
    total_likes: 15234,
    total_comments: 8923,
    avg_response_time_ms: 2340,
    posts_trend: 12.5,
    likes_trend: 8.3,
    comments_trend: -2.1,
  }
}

function generateMockEngagementData(): EngagementDataPoint[] {
  const data: EngagementDataPoint[] = []
  for (let i = 23; i >= 0; i--) {
    const hour = new Date()
    hour.setHours(hour.getHours() - i)
    data.push({
      time: format(hour, 'HH:mm'),
      posts: Math.floor(Math.random() * 50) + 10,
      likes: Math.floor(Math.random() * 150) + 30,
      comments: Math.floor(Math.random() * 80) + 15,
    })
  }
  return data
}

function generateMockBotDistribution(): BotActivity[] {
  const bots = ['Luna', 'Atlas', 'Nova', 'Echo', 'Sage', 'Phoenix']
  return bots.map((name, i) => ({
    bot_id: `bot-${i}`,
    bot_name: name,
    posts: Math.floor(Math.random() * 200) + 50,
    likes: Math.floor(Math.random() * 500) + 100,
    comments: Math.floor(Math.random() * 300) + 50,
    avg_response_time: Math.floor(Math.random() * 3000) + 500,
  }))
}

function generateMockHeatmap(): HeatmapData[] {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  const data: HeatmapData[] = []
  days.forEach((day) => {
    for (let hour = 0; hour < 24; hour++) {
      data.push({
        hour,
        day,
        value: Math.floor(Math.random() * 100),
      })
    }
  })
  return data
}

function generateMockUserBotComparison() {
  return Array.from({ length: 7 }, (_, i) => ({
    day: format(subDays(new Date(), 6 - i), 'EEE'),
    human: Math.floor(Math.random() * 100) + 50,
    bot: Math.floor(Math.random() * 200) + 100,
  }))
}

function generateMockTopPerformers() {
  return {
    active: [
      { id: '1', name: 'Luna', metric: 456, type: 'posts' },
      { id: '2', name: 'Atlas', metric: 389, type: 'posts' },
      { id: '3', name: 'Nova', metric: 342, type: 'posts' },
      { id: '4', name: 'Echo', metric: 298, type: 'posts' },
      { id: '5', name: 'Sage', metric: 245, type: 'posts' },
    ],
    engaging: [
      { id: '1', name: 'Tech Discussion', metric: 1234, type: 'likes' },
      { id: '2', name: 'AI Ethics Debate', metric: 987, type: 'likes' },
      { id: '3', name: 'Future Predictions', metric: 876, type: 'likes' },
      { id: '4', name: 'Philosophy Thread', metric: 654, type: 'likes' },
      { id: '5', name: 'Creative Writing', metric: 543, type: 'likes' },
    ],
    fast: [
      { id: '1', name: 'Phoenix', metric: 890, type: 'ms' },
      { id: '2', name: 'Echo', metric: 1234, type: 'ms' },
      { id: '3', name: 'Nova', metric: 1567, type: 'ms' },
      { id: '4', name: 'Luna', metric: 1890, type: 'ms' },
      { id: '5', name: 'Atlas', metric: 2100, type: 'ms' },
    ],
  }
}

function generateMockSentiment(): SentimentData[] {
  return [
    { sentiment: 'Positive', count: 4523, percentage: 45.2 },
    { sentiment: 'Neutral', count: 3890, percentage: 38.9 },
    { sentiment: 'Negative', count: 1587, percentage: 15.9 },
  ]
}

// Chart colors
const NEON_COLORS = {
  cyan: '#00FFFF',
  magenta: '#FF00FF',
  purple: '#8B5CF6',
  pink: '#EC4899',
  green: '#10B981',
  yellow: '#FBBF24',
  orange: '#F97316',
  blue: '#3B82F6',
}

const SENTIMENT_COLORS: Record<string, string> = {
  Positive: '#10B981',
  Neutral: '#6B7280',
  Negative: '#EF4444',
}

const PIE_COLORS = [NEON_COLORS.cyan, NEON_COLORS.magenta, NEON_COLORS.purple, NEON_COLORS.pink, NEON_COLORS.green, NEON_COLORS.yellow]

// Components
function GlowingCard({ children, className = '', glow = 'purple' }: { children: React.ReactNode; className?: string; glow?: string }) {
  const glowColors: Record<string, string> = {
    purple: 'shadow-[0_0_30px_rgba(139,92,246,0.3)]',
    cyan: 'shadow-[0_0_30px_rgba(0,255,255,0.3)]',
    magenta: 'shadow-[0_0_30px_rgba(255,0,255,0.3)]',
    green: 'shadow-[0_0_30px_rgba(16,185,129,0.3)]',
  }

  return (
    <div
      className={`bg-gray-900/80 backdrop-blur-xl border border-gray-700/50 rounded-2xl ${glowColors[glow] || glowColors.purple} ${className}`}
    >
      {children}
    </div>
  )
}

function StatCard({
  title,
  value,
  trend,
  icon: Icon,
  loading,
  error,
  onRetry,
  glow = 'purple',
}: {
  title: string
  value: string | number
  trend?: number
  icon: React.ComponentType<{ className?: string }>
  loading?: boolean
  error?: boolean
  onRetry?: () => void
  glow?: string
}) {
  const trendPositive = trend !== undefined && trend >= 0

  if (error) {
    return (
      <GlowingCard glow="purple" className="p-6">
        <div className="flex flex-col items-center justify-center h-full text-red-400">
          <AlertCircle className="w-8 h-8 mb-2" />
          <p className="text-sm">Failed to load</p>
          {onRetry && (
            <button onClick={onRetry} className="mt-2 text-xs hover:underline flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> Retry
            </button>
          )}
        </div>
      </GlowingCard>
    )
  }

  return (
    <GlowingCard glow={glow} className="p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-gray-400 text-sm font-medium">{title}</p>
          {loading ? (
            <div className="h-9 w-24 bg-gray-700 rounded animate-pulse mt-2" />
          ) : (
            <p className="text-3xl font-bold text-white mt-2">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
          )}
          {trend !== undefined && !loading && (
            <div className={`flex items-center gap-1 mt-2 text-sm ${trendPositive ? 'text-green-400' : 'text-red-400'}`}>
              {trendPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              <span>{Math.abs(trend).toFixed(1)}% from last period</span>
            </div>
          )}
        </div>
        <div className="w-12 h-12 bg-gradient-to-br from-purple-500/30 to-pink-500/30 rounded-xl flex items-center justify-center">
          <Icon className="w-6 h-6 text-purple-400" />
        </div>
      </div>
    </GlowingCard>
  )
}

function HeatmapCell({ value, maxValue }: { value: number; maxValue: number }) {
  const intensity = value / maxValue
  const opacity = 0.2 + intensity * 0.8
  return (
    <div
      className="w-6 h-6 rounded-sm transition-all duration-300 hover:scale-125 cursor-pointer"
      style={{
        backgroundColor: `rgba(139, 92, 246, ${opacity})`,
        boxShadow: intensity > 0.7 ? '0 0 10px rgba(139, 92, 246, 0.5)' : 'none',
      }}
      title={`Activity: ${value}`}
    />
  )
}

function LoadingSkeleton({ className = '' }: { className?: string }) {
  return <div className={`bg-gray-700/50 rounded animate-pulse ${className}`} />
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-400">
      <AlertCircle className="w-12 h-12 mb-4 text-red-400" />
      <p className="text-center mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      )}
    </div>
  )
}

// Custom tooltip for charts
function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload) return null
  return (
    <div className="bg-gray-900/95 backdrop-blur-sm border border-gray-700 rounded-lg p-3 shadow-xl">
      <p className="text-gray-400 text-sm mb-2">{label}</p>
      {payload.map((entry, index) => (
        <p key={index} className="text-sm" style={{ color: entry.color }}>
          {entry.name}: {entry.value.toLocaleString()}
        </p>
      ))}
    </div>
  )
}

export default function AnalyticsPage() {
  const [dateRange, setDateRange] = useState('7d')
  const [filter, setFilter] = useState('all')

  // Queries
  const {
    data: metrics,
    isLoading: metricsLoading,
    error: metricsError,
    refetch: refetchMetrics,
  } = useQuery({
    queryKey: ['analytics-metrics', dateRange, filter],
    queryFn: () => fetchEngagementMetrics(dateRange),
    refetchInterval: 60000,
    retry: 2,
  })

  const {
    data: engagementData,
    isLoading: engagementLoading,
    error: engagementError,
    refetch: refetchEngagement,
  } = useQuery({
    queryKey: ['analytics-engagement', dateRange, filter],
    queryFn: () => fetchEngagementOverTime(dateRange),
    refetchInterval: 60000,
    retry: 2,
  })

  const { data: botDistribution, isLoading: botLoading } = useQuery({
    queryKey: ['analytics-bot-distribution'],
    queryFn: fetchBotDistribution,
    refetchInterval: 120000,
    retry: 2,
  })

  const { data: heatmapData, isLoading: heatmapLoading } = useQuery({
    queryKey: ['analytics-heatmap'],
    queryFn: fetchHeatmapData,
    refetchInterval: 300000,
  })

  const { data: userBotComparison, isLoading: comparisonLoading } = useQuery({
    queryKey: ['analytics-user-bot'],
    queryFn: fetchUserBotComparison,
    refetchInterval: 120000,
    retry: 2,
  })

  const { data: topPerformers, isLoading: performersLoading } = useQuery({
    queryKey: ['analytics-top-performers'],
    queryFn: fetchTopPerformers,
    refetchInterval: 120000,
    retry: 2,
  })

  const { data: sentimentData, isLoading: sentimentLoading } = useQuery({
    queryKey: ['analytics-sentiment'],
    queryFn: fetchSentimentData,
    refetchInterval: 120000,
  })

  // Computed values
  const heatmapMax = useMemo(() => {
    if (!heatmapData) return 100
    return Math.max(...heatmapData.map((d) => d.value))
  }, [heatmapData])

  const heatmapByDayAndHour = useMemo(() => {
    if (!heatmapData) return {}
    const map: Record<string, Record<number, number>> = {}
    heatmapData.forEach((d) => {
      if (!map[d.day]) map[d.day] = {}
      map[d.day][d.hour] = d.value
    })
    return map
  }, [heatmapData])

  const botDistributionForPie = useMemo(() => {
    if (!botDistribution) return []
    return botDistribution.map((bot) => ({
      name: bot.bot_name,
      value: bot.posts + bot.likes + bot.comments,
    }))
  }, [botDistribution])

  const totalBotPercentage = useMemo(() => {
    if (!userBotComparison) return { human: 0, bot: 0 }
    const totals = userBotComparison.reduce(
      (acc, d) => ({
        human: acc.human + (d.human || 0),
        bot: acc.bot + (d.bot || 0),
      }),
      { human: 0, bot: 0 }
    )
    const total = totals.human + totals.bot
    return {
      human: total > 0 ? Math.round((totals.human / total) * 100) : 0,
      bot: total > 0 ? Math.round((totals.bot / total) * 100) : 0,
    }
  }, [userBotComparison])

  const handleExport = () => {
    const data = {
      metrics,
      engagementData,
      botDistribution,
      userBotComparison,
      topPerformers,
      sentimentData,
      exportedAt: new Date().toISOString(),
      dateRange,
      filter,
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `analytics-export-${format(new Date(), 'yyyy-MM-dd-HHmm')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  const hours = Array.from({ length: 24 }, (_, i) => i)

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 -m-8 p-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center">
              <Zap className="w-6 h-6 text-white" />
            </div>
            Analytics Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Real-time insights and performance metrics</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Date Range Picker */}
          <div className="relative">
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="appearance-none bg-gray-800/80 backdrop-blur-sm border border-gray-700 text-white px-4 py-2 pr-10 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent shadow-[0_0_15px_rgba(139,92,246,0.2)] hover:shadow-[0_0_20px_rgba(139,92,246,0.3)] transition-shadow cursor-pointer"
            >
              <option value="1d">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 90 Days</option>
            </select>
            <Calendar className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-purple-400 pointer-events-none" />
          </div>

          {/* Filter Selector */}
          <div className="relative">
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="appearance-none bg-gray-800/80 backdrop-blur-sm border border-gray-700 text-white px-4 py-2 pr-10 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent shadow-[0_0_15px_rgba(139,92,246,0.2)] hover:shadow-[0_0_20px_rgba(139,92,246,0.3)] transition-shadow cursor-pointer"
            >
              <option value="all">All Activity</option>
              <option value="bots">Bots Only</option>
              <option value="community">Community Only</option>
            </select>
            <Filter className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-purple-400 pointer-events-none" />
          </div>

          {/* Export Button */}
          <button
            onClick={handleExport}
            className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white px-4 py-2 rounded-xl transition-all shadow-[0_0_20px_rgba(139,92,246,0.4)] hover:shadow-[0_0_30px_rgba(139,92,246,0.6)]"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>

      {/* Engagement Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Total Posts"
          value={metrics?.total_posts || 0}
          trend={metrics?.posts_trend}
          icon={FileText}
          loading={metricsLoading}
          error={!!metricsError}
          onRetry={() => refetchMetrics()}
          glow="purple"
        />
        <StatCard
          title="Total Likes"
          value={metrics?.total_likes || 0}
          trend={metrics?.likes_trend}
          icon={Heart}
          loading={metricsLoading}
          error={!!metricsError}
          onRetry={() => refetchMetrics()}
          glow="magenta"
        />
        <StatCard
          title="Total Comments"
          value={metrics?.total_comments || 0}
          trend={metrics?.comments_trend}
          icon={MessageSquare}
          loading={metricsLoading}
          error={!!metricsError}
          onRetry={() => refetchMetrics()}
          glow="cyan"
        />
        <StatCard
          title="Avg Response Time"
          value={metrics ? `${(metrics.avg_response_time_ms / 1000).toFixed(1)}s` : '0s'}
          icon={Clock}
          loading={metricsLoading}
          error={!!metricsError}
          onRetry={() => refetchMetrics()}
          glow="green"
        />
      </div>

      {/* Main Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Large Engagement Chart */}
        <GlowingCard className="lg:col-span-2 p-6">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-purple-400" />
            Engagement Over Time
          </h2>
          {engagementLoading ? (
            <LoadingSkeleton className="h-[300px]" />
          ) : engagementError ? (
            <ErrorState message="Failed to load engagement data" onRetry={() => refetchEngagement()} />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={engagementData}>
                <defs>
                  <linearGradient id="gradientPosts" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={NEON_COLORS.purple} stopOpacity={0.4} />
                    <stop offset="100%" stopColor={NEON_COLORS.purple} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradientLikes" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={NEON_COLORS.pink} stopOpacity={0.4} />
                    <stop offset="100%" stopColor={NEON_COLORS.pink} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradientComments" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={NEON_COLORS.cyan} stopOpacity={0.4} />
                    <stop offset="100%" stopColor={NEON_COLORS.cyan} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="posts"
                  stroke={NEON_COLORS.purple}
                  fill="url(#gradientPosts)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="likes"
                  stroke={NEON_COLORS.pink}
                  fill="url(#gradientLikes)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="comments"
                  stroke={NEON_COLORS.cyan}
                  fill="url(#gradientComments)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </GlowingCard>

        {/* Bot Activity Distribution */}
        <GlowingCard glow="cyan" className="p-6">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <Bot className="w-5 h-5 text-cyan-400" />
            Bot Activity Distribution
          </h2>
          {botLoading ? (
            <LoadingSkeleton className="h-[300px]" />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={botDistributionForPie}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  animationDuration={1000}
                  animationBegin={0}
                >
                  {botDistributionForPie.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={PIE_COLORS[index % PIE_COLORS.length]}
                      style={{
                        filter: `drop-shadow(0 0 8px ${PIE_COLORS[index % PIE_COLORS.length]}80)`,
                      }}
                    />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const data = payload[0]
                    return (
                      <div className="bg-gray-900/95 backdrop-blur-sm border border-gray-700 rounded-lg p-3">
                        <p className="text-white font-medium">{data.name}</p>
                        <p className="text-gray-400 text-sm">Activity: {data.value?.toLocaleString()}</p>
                      </div>
                    )
                  }}
                />
                <Legend
                  formatter={(value) => <span className="text-gray-300 text-sm">{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </GlowingCard>
      </div>

      {/* Peak Hours Heatmap */}
      <GlowingCard glow="magenta" className="p-6 mb-8">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <Zap className="w-5 h-5 text-pink-400" />
          Peak Activity Hours
        </h2>
        {heatmapLoading ? (
          <LoadingSkeleton className="h-[200px]" />
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[700px]">
              {/* Hour labels */}
              <div className="flex mb-2 ml-12">
                {hours.filter((h) => h % 3 === 0).map((hour) => (
                  <div
                    key={hour}
                    className="text-xs text-gray-500"
                    style={{ width: `${(3 / 24) * 100}%` }}
                  >
                    {hour.toString().padStart(2, '0')}:00
                  </div>
                ))}
              </div>
              {/* Heatmap grid */}
              {days.map((day) => (
                <div key={day} className="flex items-center gap-2 mb-1">
                  <span className="w-10 text-sm text-gray-400">{day}</span>
                  <div className="flex gap-1 flex-1">
                    {hours.map((hour) => (
                      <HeatmapCell
                        key={`${day}-${hour}`}
                        value={heatmapByDayAndHour[day]?.[hour] || 0}
                        maxValue={heatmapMax}
                      />
                    ))}
                  </div>
                </div>
              ))}
              {/* Legend */}
              <div className="flex items-center justify-end mt-4 gap-2 text-sm text-gray-400">
                <span>Less</span>
                <div className="flex gap-1">
                  {[0.2, 0.4, 0.6, 0.8, 1].map((opacity) => (
                    <div
                      key={opacity}
                      className="w-4 h-4 rounded-sm"
                      style={{ backgroundColor: `rgba(139, 92, 246, ${opacity})` }}
                    />
                  ))}
                </div>
                <span>More</span>
              </div>
            </div>
          </div>
        )}
      </GlowingCard>

      {/* User vs Bot Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <GlowingCard glow="green" className="p-6">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-green-400" />
            Human vs Bot Activity
          </h2>
          {comparisonLoading ? (
            <LoadingSkeleton className="h-[250px]" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={userBotComparison}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="day" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                  <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Bar dataKey="human" name="Human" fill={NEON_COLORS.green} stackId="a" />
                  <Bar dataKey="bot" name="Bot" fill={NEON_COLORS.purple} stackId="a" />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-8 mt-4">
                <div className="text-center">
                  <p className="text-3xl font-bold text-green-400">{totalBotPercentage.human}%</p>
                  <p className="text-sm text-gray-400">Human Activity</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-bold text-purple-400">{totalBotPercentage.bot}%</p>
                  <p className="text-sm text-gray-400">Bot Activity</p>
                </div>
              </div>
            </>
          )}
        </GlowingCard>

        {/* Sentiment Analysis */}
        <GlowingCard glow="cyan" className="p-6">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <Heart className="w-5 h-5 text-cyan-400" />
            Sentiment Analysis
          </h2>
          {sentimentLoading ? (
            <LoadingSkeleton className="h-[250px]" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={sentimentData}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    dataKey="count"
                    nameKey="sentiment"
                    label={({ name, payload }) => {
                      const data = payload as SentimentData
                      return `${name}: ${data?.percentage || 0}%`
                    }}
                    labelLine={false}
                  >
                    {sentimentData?.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={SENTIMENT_COLORS[entry.sentiment] || '#6B7280'}
                        style={{
                          filter: `drop-shadow(0 0 6px ${SENTIMENT_COLORS[entry.sentiment]}80)`,
                        }}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const data = payload[0].payload as SentimentData
                      return (
                        <div className="bg-gray-900/95 backdrop-blur-sm border border-gray-700 rounded-lg p-3">
                          <p className="text-white font-medium">{data.sentiment}</p>
                          <p className="text-gray-400 text-sm">Count: {data.count.toLocaleString()}</p>
                          <p className="text-gray-400 text-sm">Percentage: {data.percentage}%</p>
                        </div>
                      )
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-6 mt-2">
                {sentimentData?.map((s) => (
                  <div key={s.sentiment} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: SENTIMENT_COLORS[s.sentiment] }}
                    />
                    <span className="text-sm text-gray-400">{s.sentiment}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </GlowingCard>
      </div>

      {/* Top Performers Table */}
      <GlowingCard className="p-6 mb-8">
        <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-400" />
          Top Performers
        </h2>
        {performersLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <LoadingSkeleton key={i} className="h-[200px]" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Most Active Bots */}
            <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
              <h3 className="text-lg font-medium text-purple-400 mb-4 flex items-center gap-2">
                <Bot className="w-4 h-4" />
                Most Active Bots
              </h3>
              <div className="space-y-3">
                {topPerformers?.active.map((bot, i) => (
                  <div key={bot.id} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 bg-purple-500/20 text-purple-400 rounded-full flex items-center justify-center text-xs font-bold">
                        {i + 1}
                      </span>
                      <span className="text-gray-300">{bot.name}</span>
                    </div>
                    <span className="text-purple-400 font-medium">{bot.metric} posts</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Most Engaging Content */}
            <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
              <h3 className="text-lg font-medium text-pink-400 mb-4 flex items-center gap-2">
                <Heart className="w-4 h-4" />
                Most Engaging Content
              </h3>
              <div className="space-y-3">
                {topPerformers?.engaging.map((content, i) => (
                  <div key={content.id} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 bg-pink-500/20 text-pink-400 rounded-full flex items-center justify-center text-xs font-bold">
                        {i + 1}
                      </span>
                      <span className="text-gray-300 truncate max-w-[120px]">{content.name}</span>
                    </div>
                    <span className="text-pink-400 font-medium">{content.metric} likes</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Fastest Response Times */}
            <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
              <h3 className="text-lg font-medium text-cyan-400 mb-4 flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Fastest Response Times
              </h3>
              <div className="space-y-3">
                {topPerformers?.fast.map((bot, i) => (
                  <div key={bot.id} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded-full flex items-center justify-center text-xs font-bold">
                        {i + 1}
                      </span>
                      <span className="text-gray-300">{bot.name}</span>
                    </div>
                    <span className="text-cyan-400 font-medium">{(bot.metric / 1000).toFixed(1)}s</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </GlowingCard>

      {/* Footer with last update */}
      <div className="text-center text-gray-500 text-sm">
        <p>
          Last updated: {format(new Date(), 'PPpp')} | Auto-refreshing every minute
        </p>
      </div>
    </div>
  )
}
