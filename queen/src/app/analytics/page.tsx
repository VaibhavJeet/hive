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
import { PageWrapper } from '@/components/PageWrapper'

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

// Empty state defaults
const EMPTY_METRICS: EngagementMetricsDisplay = {
  total_posts: 0,
  total_likes: 0,
  total_comments: 0,
  avg_response_time_ms: 0,
  posts_trend: 0,
  likes_trend: 0,
  comments_trend: 0,
}

const EMPTY_TOP_PERFORMERS = { active: [] as TopPerformer[], engaging: [] as TopPerformer[], fast: [] as TopPerformer[] }

// API fetch functions
async function fetchEngagementMetrics(dateRange: string): Promise<EngagementMetricsDisplay> {
  const days = dateRange === '1d' ? 1 : dateRange === '7d' ? 7 : dateRange === '30d' ? 30 : 90
  const { startDate, endDate } = getDateRange(`${days}d`)

  const [engagement, overview] = await Promise.all([
    analyticsApi.getEngagement(startDate, endDate),
    analyticsApi.getOverview(startDate, endDate).catch(() => null),
  ])

  return {
    total_posts: overview?.new_posts_period ?? Math.floor(engagement.summary.total_engagement / 3),
    total_likes: engagement.summary.total_likes,
    total_comments: engagement.summary.total_comments,
    avg_response_time_ms: 0,
    posts_trend: overview?.post_growth_rate ?? 0,
    likes_trend: overview?.user_growth_rate ?? 0,
    comments_trend: 0,
  }
}

async function fetchEngagementOverTime(dateRange: string): Promise<EngagementDataPoint[]> {
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
}

async function fetchBotDistribution(): Promise<BotActivity[]> {
  const { startDate, endDate } = getDateRange('7d')
  const botMetrics = await analyticsApi.getBotMetrics(startDate, endDate)

  return botMetrics.bots.map(bot => ({
    bot_id: bot.bot_id,
    bot_name: bot.bot_name,
    posts: bot.posts_created,
    likes: bot.likes_received,
    comments: bot.comments_received,
    avg_response_time: 0,
  }))
}

async function fetchHeatmapData(): Promise<HeatmapData[]> {
  const DAY_ABBREV: Record<string, string> = {
    Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed',
    Thursday: 'Thu', Friday: 'Fri', Saturday: 'Sat', Sunday: 'Sun',
  }
  const heatmap = await analyticsApi.getHeatmap(30, 'all')
  return heatmap.cells.map(cell => ({
    hour: cell.hour,
    day: DAY_ABBREV[cell.day_name] || cell.day_name.slice(0, 3),
    value: cell.value,
  }))
}

async function fetchUserBotComparison(): Promise<{ day: string; human: number; bot: number }[]> {
  const { startDate, endDate } = getDateRange('7d')
  const [botMetrics, userMetrics] = await Promise.all([
    analyticsApi.getBotMetrics(startDate, endDate),
    analyticsApi.getUserMetrics(startDate, endDate).catch(() => null),
  ])

  const totalBotActivity = botMetrics.bots.reduce(
    (sum, bot) => sum + bot.posts_created + bot.comments_created + bot.chat_messages_sent,
    0
  )
  const totalUserActivity = userMetrics
    ? userMetrics.users.reduce((sum, u) => sum + u.total_activity, 0)
    : 0

  // Distribute across 7 days proportionally using engagement data
  const engagement = await analyticsApi.getEngagement(startDate, endDate, 'day')

  return engagement.data_points.slice(-7).map((point, i) => {
    const dayTotal = point.total || 1
    const botRatio = totalBotActivity / (totalBotActivity + totalUserActivity || 1)
    return {
      day: format(subDays(new Date(), 6 - i), 'EEE'),
      human: Math.round(dayTotal * (1 - botRatio)),
      bot: Math.round(dayTotal * botRatio),
    }
  })
}

async function fetchTopPerformers(): Promise<{ active: TopPerformer[]; engaging: TopPerformer[]; fast: TopPerformer[] }> {
  const { startDate, endDate } = getDateRange('7d')
  const botMetrics = await analyticsApi.getBotMetrics(startDate, endDate, 'day', 10)

  const sortedByPosts = [...botMetrics.bots].sort((a, b) => b.posts_created - a.posts_created).slice(0, 5)
  const sortedByEngagement = [...botMetrics.bots].sort((a, b) => b.likes_received - a.likes_received).slice(0, 5)
  const sortedByActivity = [...botMetrics.bots].sort((a, b) => b.total_content - a.total_content).slice(0, 5)

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
    fast: sortedByActivity.map(bot => ({
      id: bot.bot_id,
      name: bot.bot_name,
      metric: bot.total_content,
      type: 'total',
    })),
  }
}

async function fetchSentimentData(): Promise<SentimentData[]> {
  const { startDate, endDate } = getDateRange('7d')
  const sentiment = await analyticsApi.getSentiment(startDate, endDate)
  const dist = sentiment.distribution

  if (dist.total_analyzed === 0) {
    return []
  }

  return [
    { sentiment: 'Positive', count: dist.positive_count, percentage: dist.positive_percentage },
    { sentiment: 'Neutral', count: dist.neutral_count, percentage: dist.neutral_percentage },
    { sentiment: 'Negative', count: dist.negative_count, percentage: dist.negative_percentage },
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
      className={`bg-[#141414]/80 backdrop-blur-xl border border-[#2a2a2a] rounded-2xl ${glowColors[glow] || glowColors.purple} ${className}`}
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
          <p className="text-[#666666] text-sm font-medium">{title}</p>
          {loading ? (
            <div className="h-9 w-24 bg-[#2a2a2a] rounded animate-pulse mt-2" />
          ) : (
            <p className="text-3xl font-bold text-foreground mt-2">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
          )}
          {trend !== undefined && !loading && (
            <div className={`flex items-center gap-1 mt-2 text-sm ${trendPositive ? 'text-[#44ff88]' : 'text-[#ff4444]'}`}>
              {trendPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              <span>{Math.abs(trend).toFixed(1)}% from last period</span>
            </div>
          )}
        </div>
        <div className="w-12 h-12 bg-gradient-to-br from-[#ff00aa]/30 to-[#00f0ff]/30 rounded-xl flex items-center justify-center">
          <Icon className="w-6 h-6 text-[#ff00aa]" />
        </div>
      </div>
    </GlowingCard>
  )
}

function HeatmapCell({ value, maxValue }: { value: number; maxValue: number }) {
  const intensity = maxValue > 0 ? value / maxValue : 0
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
  return (
    <div
      className={`
        bg-gradient-to-r from-[#252538] via-[#303048] to-[#252538]
        bg-[length:200%_100%]
        animate-shimmer
        rounded
        ${className}
      `}
    />
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-[#666666]">
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
    <div className="bg-[#141414]/95 backdrop-blur-sm border border-[#2a2a2a] rounded-lg p-3 shadow-xl">
      <p className="text-[#666666] text-sm mb-2">{label}</p>
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
    retry: 2,
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
    retry: 2,
  })

  // Computed values
  const heatmapMax = useMemo(() => {
    if (!heatmapData || heatmapData.length === 0) return 1
    return Math.max(...heatmapData.map((d) => d.value), 1)
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

  const handleRetryAll = () => {
    refetchMetrics()
    refetchEngagement()
  }

  // Page-level error state when all critical data fails to load
  const hasCriticalError = metricsError && engagementError

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  const hours = Array.from({ length: 24 }, (_, i) => i)

  // Error state UI
  if (hasCriticalError) {
    return (
      <PageWrapper>
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col items-center justify-center py-20">
            <div className="p-4 rounded-full bg-red-500/10 mb-6">
              <AlertCircle className="w-12 h-12 text-red-400" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">Failed to Load Analytics</h2>
            <p className="text-[#a0a0b0] text-center mb-6 max-w-md">
              Unable to fetch analytics data. Please check your connection and try again.
            </p>
            <button
              onClick={handleRetryAll}
              className="flex items-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors font-medium"
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
      <div className="max-w-7xl mx-auto min-h-screen -m-8 p-8">
        {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-[#ff00aa] to-[#00f0ff] rounded-xl flex items-center justify-center">
              <Zap className="w-6 h-6 text-white" />
            </div>
            Analytics Dashboard
          </h1>
          <p className="text-[#666666] mt-1">Real-time insights and performance metrics</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Date Range Picker */}
          <div className="relative">
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="appearance-none bg-[#141414] backdrop-blur-sm border border-[#2a2a2a] text-foreground px-4 py-2 pr-10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#00f0ff] focus:border-transparent shadow-[0_0_15px_rgba(0,240,255,0.2)] hover:shadow-[0_0_20px_rgba(0,240,255,0.3)] transition-shadow cursor-pointer"
            >
              <option value="1d">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 90 Days</option>
            </select>
            <Calendar className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#00f0ff] pointer-events-none" />
          </div>

          {/* Filter Selector */}
          <div className="relative">
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="appearance-none bg-[#141414] backdrop-blur-sm border border-[#2a2a2a] text-foreground px-4 py-2 pr-10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#00f0ff] focus:border-transparent shadow-[0_0_15px_rgba(0,240,255,0.2)] hover:shadow-[0_0_20px_rgba(0,240,255,0.3)] transition-shadow cursor-pointer"
            >
              <option value="all">All Activity</option>
              <option value="bots">Bots Only</option>
              <option value="community">Community Only</option>
            </select>
            <Filter className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#00f0ff] pointer-events-none" />
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
                      <div className="bg-[#141414]/95 backdrop-blur-sm border border-[#2a2a2a] rounded-lg p-3">
                        <p className="text-white font-medium">{data.name}</p>
                        <p className="text-[#666666] text-sm">Activity: {data.value?.toLocaleString()}</p>
                      </div>
                    )
                  }}
                />
                <Legend
                  formatter={(value) => <span className="text-[#a0a0a0] text-sm">{value}</span>}
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
                    className="text-xs text-[#555555]"
                    style={{ width: `${(3 / 24) * 100}%` }}
                  >
                    {hour.toString().padStart(2, '0')}:00
                  </div>
                ))}
              </div>
              {/* Heatmap grid */}
              {days.map((day) => (
                <div key={day} className="flex items-center gap-2 mb-1">
                  <span className="w-10 text-sm text-[#666666]">{day}</span>
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
              <div className="flex items-center justify-end mt-4 gap-2 text-sm text-[#666666]">
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
                  <p className="text-sm text-[#666666]">Human Activity</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-bold text-purple-400">{totalBotPercentage.bot}%</p>
                  <p className="text-sm text-[#666666]">Bot Activity</p>
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
          ) : !sentimentData || sentimentData.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[250px] text-[#666666]">
              <Heart className="w-8 h-8 mb-2 opacity-50" />
              <p className="text-sm">No sentiment data available</p>
            </div>
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
                        <div className="bg-[#141414]/95 backdrop-blur-sm border border-[#2a2a2a] rounded-lg p-3">
                          <p className="text-white font-medium">{data.sentiment}</p>
                          <p className="text-[#666666] text-sm">Count: {data.count.toLocaleString()}</p>
                          <p className="text-[#666666] text-sm">Percentage: {data.percentage}%</p>
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
                    <span className="text-sm text-[#666666]">{s.sentiment}</span>
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
            <div className="bg-[#141414]/50 rounded-xl p-4 border border-[#2a2a2a]">
              <h3 className="text-lg font-medium text-purple-400 mb-4 flex items-center gap-2">
                <Bot className="w-4 h-4" />
                Most Active Bots
              </h3>
              <div className="space-y-3">
                {(topPerformers ?? EMPTY_TOP_PERFORMERS).active.length === 0 ? (
                  <p className="text-sm text-[#666666]">No data available</p>
                ) : (
                  (topPerformers ?? EMPTY_TOP_PERFORMERS).active.map((bot, i) => (
                    <div key={bot.id} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 bg-purple-500/20 text-purple-400 rounded-full flex items-center justify-center text-xs font-bold">
                          {i + 1}
                        </span>
                        <span className="text-[#a0a0a0]">{bot.name}</span>
                      </div>
                      <span className="text-purple-400 font-medium">{bot.metric} posts</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Most Engaging Content */}
            <div className="bg-[#141414]/50 rounded-xl p-4 border border-[#2a2a2a]">
              <h3 className="text-lg font-medium text-pink-400 mb-4 flex items-center gap-2">
                <Heart className="w-4 h-4" />
                Most Engaging Content
              </h3>
              <div className="space-y-3">
                {(topPerformers ?? EMPTY_TOP_PERFORMERS).engaging.length === 0 ? (
                  <p className="text-sm text-[#666666]">No data available</p>
                ) : (
                  (topPerformers ?? EMPTY_TOP_PERFORMERS).engaging.map((content, i) => (
                    <div key={content.id} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 bg-pink-500/20 text-pink-400 rounded-full flex items-center justify-center text-xs font-bold">
                          {i + 1}
                        </span>
                        <span className="text-[#a0a0a0] truncate max-w-[120px]">{content.name}</span>
                      </div>
                      <span className="text-pink-400 font-medium">{content.metric} likes</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Most Productive */}
            <div className="bg-[#141414]/50 rounded-xl p-4 border border-[#2a2a2a]">
              <h3 className="text-lg font-medium text-cyan-400 mb-4 flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Most Productive
              </h3>
              <div className="space-y-3">
                {(topPerformers ?? EMPTY_TOP_PERFORMERS).fast.length === 0 ? (
                  <p className="text-sm text-[#666666]">No data available</p>
                ) : (
                  (topPerformers ?? EMPTY_TOP_PERFORMERS).fast.map((bot, i) => (
                    <div key={bot.id} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded-full flex items-center justify-center text-xs font-bold">
                          {i + 1}
                        </span>
                        <span className="text-[#a0a0a0]">{bot.name}</span>
                      </div>
                      <span className="text-cyan-400 font-medium">{bot.metric} total</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </GlowingCard>

        {/* Footer with last update */}
        <div className="text-center text-[#555555] text-sm">
          <p>
            Last updated: {format(new Date(), 'PPpp')} | Auto-refreshing every minute
          </p>
        </div>
      </div>
    </PageWrapper>
  )
}
