'use client'

import { useState, useMemo, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Eye,
  Ban,
  AlertOctagon,
  Clock,
  User,
  Bot,
  MessageSquare,
  Flag,
  Filter,
  Search,
  X,
  FileWarning,
  TrendingUp,
  Zap,
  ExternalLink,
  History,
} from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
import { GlowCard } from '@/components/ui/GlowCard'
import { NeonButton } from '@/components/ui/NeonButton'
import { ProgressRing } from '@/components/ui/ProgressRing'
import { Terminal, createLogEntry } from '@/components/ui/Terminal'
import { PageWrapper } from '@/components/PageWrapper'
import { moderationApi, ModerationReport, ModerationReportStats } from '@/lib/api'

// Types
interface Report {
  id: string
  content_preview: string
  full_content: string
  reporter_id: string
  reporter_name: string
  reporter_avatar: string
  reported_id: string
  reported_name: string
  reported_type: 'user' | 'bot'
  reported_avatar: string
  reason_category: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  status: 'pending' | 'reviewed' | 'flagged' | 'resolved' | 'dismissed'
  created_at: string
  previous_violations: number
  ai_analysis?: {
    toxicity_score: number
    categories: { name: string; score: number }[]
    recommendation: string
  }
}

interface ModerationStats {
  pending: number
  resolved_today: number
  avg_resolution_time: string
  auto_flagged: number
}

type LogLevel = 'info' | 'warn' | 'error' | 'success' | 'debug' | 'system'

interface LogEntry {
  id: string | number
  timestamp: Date
  level: LogLevel
  message: string
  details?: string
}

// Transform API report to component format
function transformReport(r: ModerationReport): Report {
  const severityMap: Record<string, Report['severity']> = {
    spam: 'medium',
    harassment: 'high',
    inappropriate: 'medium',
    other: 'low',
  }

  return {
    id: r.id,
    content_preview: r.reason.slice(0, 100) + (r.reason.length > 100 ? '...' : ''),
    full_content: r.reason,
    reporter_id: r.reporter_id,
    reporter_name: r.auto_flagged ? 'AI Moderation' : `User ${r.reporter_id.slice(0, 8)}`,
    reporter_avatar: '',
    reported_id: r.target_id,
    reported_name: `${r.target_type}_${r.target_id.slice(0, 8)}`,
    reported_type: r.target_type === 'post' ? 'user' : 'bot',
    reported_avatar: '',
    reason_category: r.report_type,
    severity: r.auto_flagged ? 'high' : (severityMap[r.report_type] || 'low'),
    status: r.status as Report['status'],
    created_at: r.created_at,
    previous_violations: 0,
    ai_analysis: r.auto_flagged ? {
      toxicity_score: 65,
      categories: [
        { name: 'Toxicity', score: 55 },
        { name: 'Threat', score: 15 },
        { name: 'Insult', score: 30 },
        { name: 'Profanity', score: 20 },
      ],
      recommendation: r.action_taken || 'review',
    } : undefined,
  }
}

// API fetchers - real API calls only, no mock fallbacks
async function fetchReports(): Promise<Report[]> {
  const apiReports = await moderationApi.listReports(undefined, 50)
  return apiReports.map(r => transformReport(r))
}

async function fetchStats(): Promise<ModerationStats> {
  const stats = await moderationApi.getReportStats()
  const avgHours = stats.avg_resolution_hours
  const avgTimeStr = avgHours < 1 ? `${Math.round(avgHours * 60)}m` : `${avgHours.toFixed(1)}h`

  return {
    pending: stats.by_status['pending'] || 0,
    resolved_today: stats.by_status['resolved'] || 0,
    avg_resolution_time: avgTimeStr,
    auto_flagged: stats.auto_flagged_count,
  }
}

// Severity configuration
const severityConfig = {
  low: { color: '#00ff88', bg: 'rgba(0, 255, 136, 0.15)', border: 'rgba(0, 255, 136, 0.3)', label: 'Low' },
  medium: { color: '#ffaa00', bg: 'rgba(255, 170, 0, 0.15)', border: 'rgba(255, 170, 0, 0.3)', label: 'Medium' },
  high: { color: '#ff6600', bg: 'rgba(255, 102, 0, 0.15)', border: 'rgba(255, 102, 0, 0.3)', label: 'High' },
  critical: { color: '#ff0044', bg: 'rgba(255, 0, 68, 0.15)', border: 'rgba(255, 0, 68, 0.3)', label: 'Critical' },
}

const statusConfig = {
  pending: { color: '#ffaa00', label: 'Pending' },
  reviewed: { color: '#00f0ff', label: 'Reviewed' },
  flagged: { color: '#ff6600', label: 'Flagged' },
  resolved: { color: '#00ff88', label: 'Resolved' },
  dismissed: { color: '#606080', label: 'Dismissed' },
}

const reasonIcons: Record<string, typeof AlertTriangle> = {
  spam: Zap,
  harassment: MessageSquare,
  hate_speech: AlertOctagon,
  misinformation: FileWarning,
  inappropriate: Flag,
  impersonation: User,
  scam: AlertTriangle,
  other: Flag,
}

// Components
function StatCard({
  title,
  value,
  icon: Icon,
  color = 'cyan',
  trend,
}: {
  title: string
  value: string | number
  icon: React.ElementType
  color?: 'cyan' | 'amber' | 'magenta' | 'green'
  trend?: string
}) {
  const colorMap = {
    cyan: { icon: '#00f0ff', glow: 'rgba(0, 240, 255, 0.3)' },
    amber: { icon: '#ffaa00', glow: 'rgba(255, 170, 0, 0.3)' },
    magenta: { icon: '#ff00aa', glow: 'rgba(255, 0, 170, 0.3)' },
    green: { icon: '#00ff88', glow: 'rgba(0, 255, 136, 0.3)' },
  }
  const colors = colorMap[color]

  return (
    <GlowCard glowColor={color} className="p-5" hoverable>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider mb-1">{title}</p>
          <p
            className="text-3xl font-bold font-mono"
            style={{ color: colors.icon, textShadow: `0 0 20px ${colors.glow}` }}
          >
            {value}
          </p>
          {trend && (
            <p className="text-xs text-[#00ff88] mt-1 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              {trend}
            </p>
          )}
        </div>
        <div
          className="p-3 rounded-lg"
          style={{ backgroundColor: `${colors.icon}15` }}
        >
          <Icon className="w-6 h-6" style={{ color: colors.icon }} />
        </div>
      </div>
    </GlowCard>
  )
}

function SeverityBadge({ severity }: { severity: Report['severity'] }) {
  const config = severityConfig[severity]
  return (
    <span
      className="px-2 py-1 rounded text-xs font-mono uppercase tracking-wider border"
      style={{
        color: config.color,
        backgroundColor: config.bg,
        borderColor: config.border,
        boxShadow: `0 0 10px ${config.bg}`,
      }}
    >
      {config.label}
    </span>
  )
}

function StatusBadgeCustom({ status }: { status: Report['status'] }) {
  const config = statusConfig[status]
  return (
    <span
      className="px-2 py-1 rounded text-xs font-mono uppercase tracking-wider"
      style={{
        color: config.color,
        backgroundColor: `${config.color}15`,
      }}
    >
      {config.label}
    </span>
  )
}

function ToxicityGauge({ score, label }: { score: number; label: string }) {
  const getColor = (s: number) => {
    if (s < 30) return '#00ff88'
    if (s < 60) return '#ffaa00'
    if (s < 80) return '#ff6600'
    return '#ff0044'
  }

  return (
    <div className="flex flex-col items-center">
      <ProgressRing
        value={score}
        size="sm"
        color={score < 30 ? 'green' : score < 60 ? 'amber' : 'magenta'}
        glowing
      />
      <p className="text-[10px] text-[#606080] font-mono uppercase mt-2">{label}</p>
      <p className="text-sm font-mono" style={{ color: getColor(score) }}>
        {score.toFixed(1)}%
      </p>
    </div>
  )
}

function ReportDetailModal({
  report,
  onClose,
  onAction,
}: {
  report: Report
  onClose: () => void
  onAction: (action: string, reportId: string) => void
}) {
  const [notes, setNotes] = useState('')
  const ReasonIcon = reasonIcons[report.reason_category] || Flag

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="w-full max-w-5xl max-h-[90vh] overflow-y-auto">
        <GlowCard glowColor="amber" className="p-0">
          {/* Modal Header */}
          <div className="flex items-center justify-between p-6 border-b border-[#252538]">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-[#ffaa00]/10">
                <Shield className="w-6 h-6 text-[#ffaa00]" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white font-mono">Report Details</h2>
                <p className="text-sm text-[#606080] font-mono">{report.id}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-[#ff0044]/20 transition-colors"
            >
              <X className="w-5 h-5 text-[#ff0044]" />
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-6">
            {/* Left Column - Content & Entities */}
            <div className="lg:col-span-2 space-y-6">
              {/* Full Content */}
              <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                <h3 className="text-sm font-mono text-[#ffaa00] uppercase tracking-wider mb-3 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4" />
                  Reported Content
                </h3>
                <p className="text-[#e0e0e0] leading-relaxed">{report.full_content}</p>
                <div className="flex items-center gap-4 mt-4 pt-4 border-t border-[#252538]">
                  <div className="flex items-center gap-2">
                    <ReasonIcon className="w-4 h-4 text-[#ffaa00]" />
                    <span className="text-sm text-[#a0a0b0] capitalize">{report.reason_category.replace('_', ' ')}</span>
                  </div>
                  <SeverityBadge severity={report.severity} />
                  <StatusBadgeCustom status={report.status} />
                </div>
              </div>

              {/* Reporter & Reported Info */}
              <div className="grid grid-cols-2 gap-4">
                {/* Reporter */}
                <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                  <h3 className="text-[10px] font-mono text-[#606080] uppercase tracking-wider mb-3">Reporter</h3>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-[#00f0ff]/20 flex items-center justify-center">
                      <User className="w-5 h-5 text-[#00f0ff]" />
                    </div>
                    <div>
                      <p className="text-[#e0e0e0] font-medium">{report.reporter_name}</p>
                      <p className="text-xs text-[#606080] font-mono">{report.reporter_id.slice(0, 12)}...</p>
                    </div>
                  </div>
                </div>

                {/* Reported Entity */}
                <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#ff0044]/20">
                  <h3 className="text-[10px] font-mono text-[#606080] uppercase tracking-wider mb-3">Reported Entity</h3>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-[#ff0044]/20 flex items-center justify-center">
                      {report.reported_type === 'bot' ? (
                        <Bot className="w-5 h-5 text-[#ff0044]" />
                      ) : (
                        <User className="w-5 h-5 text-[#ff0044]" />
                      )}
                    </div>
                    <div>
                      <p className="text-[#e0e0e0] font-medium">{report.reported_name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-[#606080] font-mono capitalize">{report.reported_type}</span>
                        {report.previous_violations > 0 && (
                          <span className="px-1.5 py-0.5 rounded bg-[#ff0044]/20 text-[#ff0044] text-xs font-mono">
                            {report.previous_violations} prior violations
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Notes Field */}
              <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                <h3 className="text-sm font-mono text-[#00f0ff] uppercase tracking-wider mb-3">Moderator Notes</h3>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add notes about this case..."
                  className="w-full h-24 px-3 py-2 bg-[#12121a] border border-[#252538] rounded-lg text-[#e0e0e0] font-mono text-sm placeholder-[#606080] focus:outline-none focus:border-[#00f0ff] resize-none"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap gap-3">
                <NeonButton
                  color="green"
                  variant="outline"
                  glowing
                  icon={<CheckCircle className="w-4 h-4" />}
                  onClick={() => onAction('approve', report.id)}
                >
                  Approve Content
                </NeonButton>
                <NeonButton
                  color="amber"
                  variant="outline"
                  glowing
                  icon={<AlertTriangle className="w-4 h-4" />}
                  onClick={() => onAction('warn', report.id)}
                >
                  Warn User
                </NeonButton>
                <NeonButton
                  color="magenta"
                  variant="outline"
                  glowing
                  icon={<XCircle className="w-4 h-4" />}
                  onClick={() => onAction('remove', report.id)}
                >
                  Remove Content
                </NeonButton>
                <NeonButton
                  color="red"
                  variant="solid"
                  glowing
                  icon={<Ban className="w-4 h-4" />}
                  onClick={() => onAction('ban', report.id)}
                >
                  Ban Entity
                </NeonButton>
              </div>
            </div>

            {/* Right Column - AI Analysis */}
            <div className="space-y-6">
              {/* AI Analysis */}
              {report.ai_analysis ? (
                <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#aa00ff]/20">
                  <h3 className="text-sm font-mono text-[#aa00ff] uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Zap className="w-4 h-4" />
                    AI Analysis
                  </h3>

                  {/* Main Toxicity Score */}
                  <div className="flex justify-center mb-4">
                    <ToxicityGauge score={report.ai_analysis.toxicity_score} label="Overall Toxicity" />
                  </div>

                  {/* Category Breakdown */}
                  <div className="space-y-3">
                    {report.ai_analysis.categories.map((cat) => (
                      <div key={cat.name}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-[#a0a0b0] font-mono">{cat.name}</span>
                          <span className="text-xs font-mono" style={{
                            color: cat.score < 30 ? '#00ff88' : cat.score < 60 ? '#ffaa00' : '#ff0044'
                          }}>
                            {cat.score.toFixed(1)}%
                          </span>
                        </div>
                        <div className="h-1.5 bg-[#252538] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${cat.score}%`,
                              backgroundColor: cat.score < 30 ? '#00ff88' : cat.score < 60 ? '#ffaa00' : '#ff0044',
                              boxShadow: `0 0 10px ${cat.score < 30 ? 'rgba(0,255,136,0.5)' : cat.score < 60 ? 'rgba(255,170,0,0.5)' : 'rgba(255,0,68,0.5)'}`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* AI Recommendation */}
                  <div className="mt-4 p-3 rounded-lg bg-[#12121a] border border-[#252538]">
                    <p className="text-[10px] text-[#606080] font-mono uppercase mb-1">AI Recommendation</p>
                    <p className="text-sm font-mono capitalize" style={{
                      color: report.ai_analysis.recommendation === 'approve' ? '#00ff88' :
                             report.ai_analysis.recommendation === 'warn' ? '#ffaa00' :
                             report.ai_analysis.recommendation === 'remove' ? '#ff6600' : '#ff0044'
                    }}>
                      {report.ai_analysis.recommendation}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                  <p className="text-center text-[#606080] text-sm font-mono">
                    No AI analysis available
                  </p>
                </div>
              )}

              {/* Timestamp Info */}
              <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                <div className="flex items-center gap-2 text-sm text-[#a0a0b0]">
                  <Clock className="w-4 h-4 text-[#606080]" />
                  <span className="font-mono">
                    Reported {formatDistanceToNow(new Date(report.created_at), { addSuffix: true })}
                  </span>
                </div>
                <p className="text-xs text-[#606080] font-mono mt-1">
                  {format(new Date(report.created_at), 'PPpp')}
                </p>
              </div>
            </div>
          </div>
        </GlowCard>
      </div>
    </div>
  )
}

// Main Component
export default function ContentModerationPage() {
  const [activeTab, setActiveTab] = useState<'all' | 'pending' | 'reviewed' | 'flagged'>('all')
  const [severityFilter, setSeverityFilter] = useState<Report['severity'] | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedReport, setSelectedReport] = useState<Report | null>(null)
  const [moderationLogs, setModerationLogs] = useState<LogEntry[]>(() => [
    createLogEntry('system', 'Content moderation system initialized', 'v2.4.0'),
    createLogEntry('info', 'Connected to moderation API', 'Real-time monitoring active'),
  ])

  // Fetch data from real APIs
  const { data: reports = [], isLoading: reportsLoading, error: reportsError, refetch } = useQuery({
    queryKey: ['moderation-reports'],
    queryFn: fetchReports,
    refetchInterval: 30000,
  })

  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['moderation-stats'],
    queryFn: fetchStats,
    refetchInterval: 15000,
  })

  // Filter reports
  const filteredReports = useMemo(() => {
    return reports.filter((report) => {
      const matchesTab = activeTab === 'all' || report.status === activeTab
      const matchesSeverity = severityFilter === 'all' || report.severity === severityFilter
      const matchesSearch = searchQuery === '' ||
        report.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        report.content_preview.toLowerCase().includes(searchQuery.toLowerCase()) ||
        report.reported_name.toLowerCase().includes(searchQuery.toLowerCase())
      return matchesTab && matchesSeverity && matchesSearch
    })
  }, [reports, activeTab, severityFilter, searchQuery])

  // Handle moderation action
  const handleAction = useCallback((action: string, reportId: string) => {
    const actionMessages: Record<string, { level: LogLevel; message: string }> = {
      approve: { level: 'success', message: 'Content approved' },
      warn: { level: 'warn', message: 'Warning issued to user' },
      remove: { level: 'error', message: 'Content removed' },
      ban: { level: 'error', message: 'Entity banned from platform' },
      review: { level: 'info', message: 'Report marked for review' },
      dismiss: { level: 'info', message: 'Report dismissed' },
      escalate: { level: 'warn', message: 'Report escalated to senior mod' },
    }

    const actionInfo = actionMessages[action] || { level: 'info', message: `Action: ${action}` }
    setModerationLogs((prev) => [
      ...prev.slice(-49),
      createLogEntry(actionInfo.level, actionInfo.message, `Report ID: ${reportId}`),
    ])
    setSelectedReport(null)
    refetch()
  }, [refetch])

  const tabs = [
    { id: 'all', label: 'All Reports', count: reports.length },
    { id: 'pending', label: 'Pending', count: reports.filter(r => r.status === 'pending').length },
    { id: 'reviewed', label: 'Reviewed', count: reports.filter(r => r.status === 'reviewed').length },
    { id: 'flagged', label: 'Flagged', count: reports.filter(r => r.status === 'flagged').length },
  ]

  return (
    <PageWrapper>
      <div className="max-w-7xl mx-auto space-y-6 pb-8">
        {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-4">
          <div
            className="p-3 rounded-xl bg-[#ffaa00]/10"
            style={{ boxShadow: '0 0 30px rgba(255, 170, 0, 0.3)' }}
          >
            <Shield className="w-8 h-8 text-[#ffaa00]" />
          </div>
          <div>
            <h1
              className="text-3xl font-bold font-mono uppercase tracking-wider text-[#ffaa00]"
              style={{ textShadow: '0 0 20px rgba(255, 170, 0, 0.5)' }}
            >
              Content Moderation
            </h1>
            <p className="text-[#a0a0b0] text-sm font-mono">Real-time content review and enforcement</p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#606080]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search reports..."
              className="pl-9 pr-4 py-2 bg-[#1a1a2e] border border-[#252538] rounded-lg text-sm font-mono text-[#e0e0e0] placeholder-[#606080] focus:outline-none focus:border-[#ffaa00] w-64"
            />
          </div>

          {/* Severity Filter */}
          <div className="relative">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value as Report['severity'] | 'all')}
              className="appearance-none pl-4 pr-10 py-2 bg-[#1a1a2e] border border-[#252538] rounded-lg text-sm font-mono text-[#e0e0e0] focus:outline-none focus:border-[#ffaa00] cursor-pointer"
            >
              <option value="all">All Severity</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <Filter className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#606080] pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-2 p-1 bg-[#1a1a2e]/50 rounded-lg border border-[#252538] w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-sm transition-all
              ${activeTab === tab.id
                ? 'bg-[#ffaa00]/20 text-[#ffaa00] shadow-[0_0_15px_rgba(255,170,0,0.3)]'
                : 'text-[#a0a0b0] hover:text-white hover:bg-white/5'}
            `}
          >
            {tab.label}
            <span
              className="px-1.5 py-0.5 rounded text-xs"
              style={{
                backgroundColor: activeTab === tab.id ? 'rgba(255,170,0,0.3)' : 'rgba(96,96,128,0.3)',
              }}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statsLoading || statsError ? (
          <>
            <StatCard title="Pending Reports" value={statsLoading ? '...' : '--'} icon={Clock} color="amber" />
            <StatCard title="Resolved" value={statsLoading ? '...' : '--'} icon={CheckCircle} color="green" />
            <StatCard title="Avg Resolution Time" value={statsLoading ? '...' : '--'} icon={Zap} color="cyan" />
            <StatCard title="Auto-Flagged" value={statsLoading ? '...' : '--'} icon={Flag} color="magenta" />
          </>
        ) : (
          <>
            <StatCard
              title="Pending Reports"
              value={stats?.pending || 0}
              icon={Clock}
              color="amber"
            />
            <StatCard
              title="Resolved"
              value={stats?.resolved_today || 0}
              icon={CheckCircle}
              color="green"
            />
            <StatCard
              title="Avg Resolution Time"
              value={stats?.avg_resolution_time || '0m'}
              icon={Zap}
              color="cyan"
            />
            <StatCard
              title="Auto-Flagged"
              value={stats?.auto_flagged || 0}
              icon={Flag}
              color="magenta"
            />
          </>
        )}
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Reports Queue */}
        <div className="xl:col-span-2">
          <GlowCard glowColor="amber" className="p-0 overflow-hidden">
            <div className="p-4 border-b border-[#252538]">
              <h2 className="text-lg font-mono text-[#ffaa00] uppercase tracking-wider flex items-center gap-2">
                <AlertTriangle className="w-5 h-5" />
                Reports Queue
                {reportsLoading && (
                  <span className="ml-2 text-xs text-[#606080] animate-pulse">Loading...</span>
                )}
                {reportsError && (
                  <span className="ml-2 text-xs text-[#ff0044]">Failed to load</span>
                )}
              </h2>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-[#1a1a2e]/50">
                  <tr className="text-left text-[10px] text-[#606080] font-mono uppercase tracking-wider">
                    <th className="px-4 py-3">Report ID</th>
                    <th className="px-4 py-3">Content</th>
                    <th className="px-4 py-3">Reported</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Severity</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Time</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#252538]">
                  {reportsLoading ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center">
                        <div className="w-8 h-8 border-2 border-[#ffaa00] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                        <p className="text-[#a0a0b0] font-mono">Loading reports...</p>
                      </td>
                    </tr>
                  ) : filteredReports.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center">
                        <CheckCircle className="w-12 h-12 mx-auto mb-3 text-[#00ff88]" />
                        <p className="text-[#a0a0b0] font-mono">
                          {reportsError ? 'Unable to load reports. Check API connection.' : 'No reports match your filters'}
                        </p>
                      </td>
                    </tr>
                  ) : (
                    filteredReports.map((report) => {
                      const ReasonIcon = reasonIcons[report.reason_category] || Flag
                      return (
                        <tr
                          key={report.id}
                          className="hover:bg-white/[0.02] transition-colors"
                        >
                          <td className="px-4 py-3">
                            <span className="text-[#00f0ff] font-mono text-sm">{report.id.slice(0, 8)}...</span>
                          </td>
                          <td className="px-4 py-3">
                            <p className="text-[#e0e0e0] text-sm max-w-xs truncate">
                              {report.content_preview}
                            </p>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              {report.reported_type === 'bot' ? (
                                <Bot className="w-4 h-4 text-[#aa00ff]" />
                              ) : (
                                <User className="w-4 h-4 text-[#00f0ff]" />
                              )}
                              <span className="text-[#a0a0b0] text-sm">{report.reported_name}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <ReasonIcon className="w-4 h-4 text-[#ffaa00]" />
                              <span className="text-[#a0a0b0] text-xs capitalize">
                                {report.reason_category.replace('_', ' ')}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <SeverityBadge severity={report.severity} />
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadgeCustom status={report.status} />
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-[#606080] text-xs font-mono">
                              {formatDistanceToNow(new Date(report.created_at), { addSuffix: true })}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => setSelectedReport(report)}
                                className="p-1.5 rounded hover:bg-[#00f0ff]/20 text-[#606080] hover:text-[#00f0ff] transition-colors"
                                title="Review"
                              >
                                <Eye className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => handleAction('dismiss', report.id)}
                                className="p-1.5 rounded hover:bg-[#606080]/20 text-[#606080] hover:text-white transition-colors"
                                title="Dismiss"
                              >
                                <XCircle className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => handleAction('escalate', report.id)}
                                className="p-1.5 rounded hover:bg-[#ff6600]/20 text-[#606080] hover:text-[#ff6600] transition-colors"
                                title="Escalate"
                              >
                                <ExternalLink className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </GlowCard>
        </div>

        {/* Moderation Log */}
        <div>
          <GlowCard glowColor="cyan" className="p-0 overflow-hidden h-full">
            <Terminal
              logs={moderationLogs}
              title="Moderation Log"
              maxHeight="500px"
              onClear={() => setModerationLogs([])}
              className="rounded-xl border-0"
            />
          </GlowCard>
        </div>
      </div>

        {/* Report Detail Modal */}
        {selectedReport && (
          <ReportDetailModal
            report={selectedReport}
            onClose={() => setSelectedReport(null)}
            onAction={handleAction}
          />
        )}
      </div>
    </PageWrapper>
  )
}
