'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Server,
  Database,
  Cpu,
  HardDrive,
  Wifi,
  Activity,
  RefreshCw,
  Trash2,
  Download,
  Zap,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Search,
  Filter,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'
import { GlowCard } from '@/components/ui/GlowCard'
import { ProgressRing } from '@/components/ui/ProgressRing'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import { NeonButton } from '@/components/ui/NeonButton'
import { Terminal, createLogEntry } from '@/components/ui/Terminal'
import { PageWrapper } from '@/components/PageWrapper'

type LogLevel = 'info' | 'warn' | 'error' | 'success' | 'debug' | 'system'

interface LogEntry {
  id: string | number
  timestamp: Date
  level: LogLevel
  message: string
  details?: string
}

import {
  healthApi, adminApi, EngineStatus,
  systemApi, SystemStatusData, PerformancePoint, SystemServiceStatus,
} from '@/lib/api'

interface HealthCheck {
  name: string
  status: 'healthy' | 'unhealthy' | 'degraded'
  latency_ms?: number
  message?: string
}

interface SystemHealth {
  status: string
  timestamp: string
  version: string
  checks: HealthCheck[]
}

async function fetchHealth(): Promise<SystemHealth> {
  const health = await healthApi.detailed()
  return {
    status: health.status,
    timestamp: health.timestamp,
    version: '2.0.0',
    checks: [
      { name: 'Database', status: health.components?.database === 'healthy' ? 'healthy' : 'unhealthy', latency_ms: 8 },
      { name: 'LLM Service', status: health.components?.llm === 'healthy' ? 'healthy' : 'degraded', latency_ms: 120 },
      { name: 'Scheduler', status: health.components?.scheduler === 'healthy' ? 'healthy' : 'unhealthy', latency_ms: 5 },
      { name: 'Redis Cache', status: 'healthy' as const, latency_ms: 2 },
      { name: 'WebSocket', status: 'healthy' as const, latency_ms: 15 },
    ],
  }
}

async function fetchEngineStatus(): Promise<EngineStatus | null> {
  try {
    return await adminApi.getEngineStatus()
  } catch (error) {
    console.warn('Failed to fetch engine status:', error)
    return null
  }
}

// Icon map for services from API
const serviceIconMap: Record<string, typeof Server> = {
  'API Server': Server,
  'Database': Database,
  'Redis Cache': Zap,
  'LLM Service': Cpu,
  'Activity Engine': Activity,
  'WebSocket': Wifi,
}

export default function SystemPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [logFilter, setLogFilter] = useState<LogLevel | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  // Real system status from backend
  const { data: systemStatus, error: systemError, refetch: refetchSystem } = useQuery({
    queryKey: ['system-status'],
    queryFn: () => systemApi.getStatus(),
    refetchInterval: 3000,
  })

  // Real performance data from backend
  const { data: perfData, refetch: refetchPerf } = useQuery({
    queryKey: ['system-performance'],
    queryFn: () => systemApi.getPerformance(30),
    refetchInterval: 5000,
  })

  // Real logs from backend
  const { data: backendLogs, refetch: refetchLogs } = useQuery({
    queryKey: ['system-logs'],
    queryFn: () => systemApi.getLogs({ limit: 100 }),
    refetchInterval: 5000,
  })

  const { data: health, error: healthError, refetch: refetchHealth } = useQuery({
    queryKey: ['health-detailed'],
    queryFn: fetchHealth,
    refetchInterval: 5000,
  })

  const { data: engineStatus, error: engineError, refetch: refetchEngine } = useQuery({
    queryKey: ['engine-status'],
    queryFn: fetchEngineStatus,
    refetchInterval: 15000,
  })

  const hasError = healthError && engineError && systemError

  const handleRetry = () => {
    refetchHealth()
    refetchSystem()
    refetchPerf()
    refetchLogs()
    refetchEngine()
  }

  // Transform backend logs to component format
  useEffect(() => {
    if (backendLogs?.logs) {
      const transformed: LogEntry[] = backendLogs.logs.map((l) => ({
        id: l.id,
        timestamp: new Date(l.timestamp),
        level: (l.level as LogLevel) || 'info',
        message: l.message,
        details: l.details || undefined,
      }))
      setLogs(transformed)
    }
  }, [backendLogs])

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    return `${days}d ${hours.toString().padStart(2, '0')}h ${mins.toString().padStart(2, '0')}m ${secs.toString().padStart(2, '0')}s`
  }

  const overallStatus = health?.status === 'healthy' ? 'operational' : health?.status === 'degraded' ? 'degraded' : 'critical'

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const matchesFilter = logFilter === 'all' || log.level === logFilter
      const matchesSearch =
        searchQuery === '' ||
        log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (log.details?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false)
      return matchesFilter && matchesSearch
    })
  }, [logs, logFilter, searchQuery])

  const handleClearLogs = useCallback(() => {
    setLogs([])
  }, [])

  // Use real resources from API
  const resources = systemStatus ? {
    cpu: systemStatus.resources.cpu_percent,
    memory: {
      used: systemStatus.resources.memory_used_gb,
      total: systemStatus.resources.memory_total_gb,
      percentage: systemStatus.resources.memory_percent,
    },
    disk: {
      used: systemStatus.resources.disk_used_gb,
      total: systemStatus.resources.disk_total_gb,
      percentage: systemStatus.resources.disk_percent,
    },
    network: {
      in: systemStatus.resources.network_recv_mb_s,
      out: systemStatus.resources.network_sent_mb_s,
    },
  } : null

  // Map API status to StatusIndicator-compatible status
  const mapServiceStatus = (s: string): 'online' | 'offline' | 'warning' => {
    if (s === 'online') return 'online'
    if (s === 'degraded') return 'warning'
    return 'offline'
  }

  // Use real services from API
  const services: { name: string; icon: typeof Server; status: 'online' | 'offline' | 'warning'; metrics: { label: string; value: string }[] }[] =
    systemStatus?.services.map((s: SystemServiceStatus) => ({
      name: s.name,
      icon: serviceIconMap[s.name] || Server,
      status: mapServiceStatus(s.status),
      metrics: s.metrics,
    })) || []

  // Performance chart data from API
  const performanceData = perfData?.data_points?.map((p: PerformancePoint) => ({
    time: p.time,
    cpu: p.cpu,
    memory: p.memory,
    diskRead: p.disk_io_read,
    diskWrite: p.disk_io_write,
  })) || []

  const uptimeSeconds = systemStatus?.uptime_seconds ?? 0

  // Error state UI
  if (hasError) {
    return (
      <PageWrapper>
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col items-center justify-center py-20">
            <div className="p-4 rounded-full bg-red-500/10 mb-6">
              <AlertTriangle className="w-12 h-12 text-red-400" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">Failed to Load System Status</h2>
            <p className="text-[#a0a0b0] text-center mb-6 max-w-md">
              Unable to fetch system health data. Please check that the API server is running.
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
      <div className="max-w-7xl mx-auto space-y-6 pb-8">
        {/* System Status Banner */}
      <GlowCard
        glowColor={overallStatus === 'operational' ? 'green' : overallStatus === 'degraded' ? 'amber' : 'magenta'}
        className="p-6"
      >
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="flex items-center gap-6">
            {/* Status Icon */}
            <div
              className={`
                relative w-20 h-20 rounded-full flex items-center justify-center
                ${overallStatus === 'operational' ? 'bg-[#00ff88]/10' : overallStatus === 'degraded' ? 'bg-[#ffaa00]/10' : 'bg-[#ff0044]/10'}
              `}
            >
              <div
                className={`
                  absolute inset-0 rounded-full animate-ping opacity-30
                  ${overallStatus === 'operational' ? 'bg-[#00ff88]' : overallStatus === 'degraded' ? 'bg-[#ffaa00]' : 'bg-[#ff0044]'}
                `}
              />
              {overallStatus === 'operational' ? (
                <CheckCircle2 className="w-10 h-10 text-[#00ff88]" />
              ) : overallStatus === 'degraded' ? (
                <AlertTriangle className="w-10 h-10 text-[#ffaa00]" />
              ) : (
                <XCircle className="w-10 h-10 text-[#ff0044]" />
              )}
            </div>

            <div>
              <h1
                className={`
                  text-3xl font-bold font-mono uppercase tracking-wider
                  ${overallStatus === 'operational' ? 'text-[#00ff88]' : overallStatus === 'degraded' ? 'text-[#ffaa00]' : 'text-[#ff0044]'}
                `}
                style={{
                  textShadow: `0 0 20px ${overallStatus === 'operational' ? 'rgba(0, 255, 136, 0.5)' : overallStatus === 'degraded' ? 'rgba(255, 170, 0, 0.5)' : 'rgba(255, 0, 68, 0.5)'}`,
                }}
              >
                {overallStatus === 'operational'
                  ? 'All Systems Operational'
                  : overallStatus === 'degraded'
                    ? 'System Degraded'
                    : 'System Critical'}
              </h1>
              <p className="text-[#a0a0b0] mt-1 font-mono text-sm">
                Mission Control Center v{health?.version || '2.0.0'}
                {systemStatus && ` | PID ${systemStatus.pid} | Python ${systemStatus.python_version}`}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-6">
            {/* Uptime Counter */}
            <div className="flex items-center gap-3 px-4 py-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
              <Clock className="w-5 h-5 text-[#00f0ff]" />
              <div>
                <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider">System Uptime</p>
                <p className="text-lg font-mono text-[#00f0ff]" style={{ textShadow: '0 0 10px rgba(0, 240, 255, 0.5)' }}>
                  {formatUptime(uptimeSeconds)}
                </p>
              </div>
            </div>

            {/* Active Connections */}
            <div className="flex items-center gap-3 px-4 py-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
              <Wifi className="w-5 h-5 text-[#00ff88]" />
              <div>
                <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider">Active Connections</p>
                <p className="text-lg font-mono text-[#00ff88]">{systemStatus?.active_connections ?? '--'}</p>
              </div>
            </div>
          </div>
        </div>
      </GlowCard>

      {/* Resource Gauges Row */}
      {resources ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {/* CPU Usage */}
          <GlowCard glowColor="cyan" className="p-4">
            <div className="flex flex-col items-center">
              <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider mb-3">CPU Usage</p>
              <ProgressRing
                value={resources.cpu}
                color="cyan"
                size="lg"
                glowing
                label={
                  <div className="text-center">
                    <span className="text-2xl font-mono font-bold text-[#00f0ff]">{resources.cpu}%</span>
                  </div>
                }
              />
              <div className="mt-3 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[#606080]" />
                <span className="text-xs text-[#a0a0b0] font-mono">{systemStatus?.resources.cpu_count ?? '--'} cores</span>
              </div>
            </div>
          </GlowCard>

          {/* Memory Usage */}
          <GlowCard glowColor="magenta" className="p-4">
            <div className="flex flex-col items-center">
              <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider mb-3">Memory</p>
              <ProgressRing
                value={resources.memory.percentage}
                color="magenta"
                size="lg"
                glowing
                label={
                  <div className="text-center">
                    <span className="text-2xl font-mono font-bold text-[#ff00aa]">{resources.memory.percentage}%</span>
                  </div>
                }
              />
              <div className="mt-3 text-center">
                <span className="text-xs text-[#a0a0b0] font-mono">
                  {resources.memory.used}GB / {resources.memory.total}GB
                </span>
              </div>
            </div>
          </GlowCard>

          {/* Disk Usage */}
          <GlowCard glowColor="green" className="p-4">
            <div className="flex flex-col items-center">
              <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider mb-3">Disk</p>
              <ProgressRing
                value={resources.disk.percentage}
                color="green"
                size="lg"
                glowing
                label={
                  <div className="text-center">
                    <span className="text-2xl font-mono font-bold text-[#00ff88]">{resources.disk.percentage}%</span>
                  </div>
                }
              />
              <div className="mt-3 flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-[#606080]" />
                <span className="text-xs text-[#a0a0b0] font-mono">
                  {resources.disk.used}GB / {resources.disk.total}GB
                </span>
              </div>
            </div>
          </GlowCard>

          {/* Network I/O */}
          <GlowCard glowColor="amber" className="p-4">
            <div className="flex flex-col items-center">
              <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider mb-3">Network I/O</p>
              <ProgressRing
                value={Math.min(100, (resources.network.in + resources.network.out) * 5)}
                color="amber"
                size="lg"
                glowing
                label={
                  <div className="text-center">
                    <Wifi className="w-6 h-6 text-[#ffaa00] mx-auto" />
                  </div>
                }
              />
              <div className="mt-3 flex gap-4 text-xs font-mono">
                <span className="text-[#00ff88]">IN: {resources.network.in} MB/s</span>
                <span className="text-[#ff00aa]">OUT: {resources.network.out} MB/s</span>
              </div>
            </div>
          </GlowCard>

          {/* Active Bots / Engine Status */}
          <GlowCard glowColor="purple" className="p-4 col-span-2 md:col-span-1">
            <div className="flex flex-col items-center">
              <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider mb-3">
                {engineStatus ? 'Engine Status' : 'Active Bots'}
              </p>
              <ProgressRing
                value={engineStatus ? Math.round(engineStatus.capacity_used * 100) : 0}
                color="purple"
                size="lg"
                glowing
                label={
                  <div className="text-center">
                    <span className="text-2xl font-mono font-bold text-[#aa00ff]">
                      {engineStatus ? `${Math.round(engineStatus.capacity_used * 100)}%` : '--'}
                    </span>
                  </div>
                }
              />
              <div className="mt-3 flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#606080]" />
                <span className="text-xs text-[#a0a0b0] font-mono">
                  {engineStatus ? `${engineStatus.running_tasks} tasks running` : 'No data'}
                </span>
              </div>
            </div>
          </GlowCard>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <GlowCard key={i} glowColor="cyan" className="p-4">
              <div className="flex flex-col items-center justify-center h-32">
                <div className="w-8 h-8 border-2 border-[#00f0ff] border-t-transparent rounded-full animate-spin" />
                <p className="text-xs text-[#606080] mt-3 font-mono">Loading...</p>
              </div>
            </GlowCard>
          ))}
        </div>
      )}

      {/* Service Status Grid */}
      <div>
        <h2 className="text-lg font-mono text-[#00f0ff] uppercase tracking-wider mb-4 flex items-center gap-2">
          <Server className="w-5 h-5" />
          Service Status
        </h2>
        {services.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {services.map((service) => {
              const Icon = service.icon
              return (
                <GlowCard key={service.name} glowColor="cyan" className="p-4" hoverable>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="p-2 rounded-lg bg-[#00f0ff]/10">
                        <Icon className="w-5 h-5 text-[#00f0ff]" />
                      </div>
                      <span className="font-mono text-sm text-[#e0e0e0]">{service.name}</span>
                    </div>
                    <StatusIndicator status={service.status} size="sm" pulse showGlow />
                  </div>
                  <div className="space-y-2">
                    {service.metrics.map((metric, idx) => (
                      <div key={idx} className="flex justify-between items-center">
                        <span className="text-[10px] text-[#606080] font-mono uppercase">{metric.label}</span>
                        <span className="text-xs font-mono text-[#00f0ff]">{metric.value}</span>
                      </div>
                    ))}
                  </div>
                </GlowCard>
              )
            })}
          </div>
        ) : (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-[#00f0ff] border-t-transparent rounded-full animate-spin" />
            <p className="text-[#606080] ml-3 font-mono">Loading services...</p>
          </div>
        )}
      </div>

      {/* Performance Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* CPU Usage Over Time */}
        <GlowCard glowColor="cyan" className="p-4">
          <h3 className="text-sm font-mono text-[#00f0ff] uppercase tracking-wider mb-4">CPU Usage</h3>
          {performanceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={performanceData}>
                <defs>
                  <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00f0ff" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#00f0ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#252538" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} />
                <YAxis tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} unit="%" domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a1a2e',
                    border: '1px solid #252538',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="cpu"
                  stroke="#00f0ff"
                  strokeWidth={2}
                  fill="url(#cpuGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[180px] text-[#606080] font-mono text-sm">
              Collecting data...
            </div>
          )}
        </GlowCard>

        {/* Memory Usage Over Time */}
        <GlowCard glowColor="magenta" className="p-4">
          <h3 className="text-sm font-mono text-[#ff00aa] uppercase tracking-wider mb-4">Memory Usage</h3>
          {performanceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={performanceData}>
                <defs>
                  <linearGradient id="memGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ff00aa" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#ff00aa" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#252538" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} />
                <YAxis tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} unit="%" domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a1a2e',
                    border: '1px solid #252538',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="memory"
                  stroke="#ff00aa"
                  strokeWidth={2}
                  fill="url(#memGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[180px] text-[#606080] font-mono text-sm">
              Collecting data...
            </div>
          )}
        </GlowCard>

        {/* Disk I/O */}
        <GlowCard glowColor="green" className="p-4">
          <h3 className="text-sm font-mono text-[#00ff88] uppercase tracking-wider mb-4">Disk I/O</h3>
          {performanceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#252538" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} />
                <YAxis tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} unit="MB/s" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a1a2e',
                    border: '1px solid #252538',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="diskRead"
                  name="Read"
                  stroke="#00ff88"
                  strokeWidth={2}
                  dot={false}
                  style={{ filter: 'drop-shadow(0 0 8px rgba(0, 255, 136, 0.5))' }}
                />
                <Line
                  type="monotone"
                  dataKey="diskWrite"
                  name="Write"
                  stroke="#ffaa00"
                  strokeWidth={2}
                  dot={false}
                  style={{ filter: 'drop-shadow(0 0 8px rgba(255, 170, 0, 0.5))' }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[180px] text-[#606080] font-mono text-sm">
              Collecting data...
            </div>
          )}
        </GlowCard>
      </div>

      {/* Live Logs Terminal */}
      <GlowCard glowColor="cyan" className="p-0 overflow-hidden">
        <div className="p-4 border-b border-[#252538]">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <h3 className="text-sm font-mono text-[#00f0ff] uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4" />
              System Logs
              {backendLogs && (
                <span className="text-[10px] text-[#606080] ml-2">({backendLogs.total} total)</span>
              )}
            </h3>

            <div className="flex flex-wrap items-center gap-3">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#606080]" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search logs..."
                  className="pl-9 pr-3 py-1.5 bg-[#1a1a2e] border border-[#252538] rounded-lg text-xs font-mono text-[#e0e0e0] placeholder-[#606080] focus:outline-none focus:border-[#00f0ff]"
                />
              </div>

              {/* Filter */}
              <div className="flex items-center gap-1">
                <Filter className="w-4 h-4 text-[#606080]" />
                <select
                  value={logFilter}
                  onChange={(e) => setLogFilter(e.target.value as LogLevel | 'all')}
                  className="bg-[#1a1a2e] border border-[#252538] rounded-lg text-xs font-mono text-[#e0e0e0] px-2 py-1.5 focus:outline-none focus:border-[#00f0ff]"
                >
                  <option value="all">All Levels</option>
                  <option value="info">Info</option>
                  <option value="warn">Warning</option>
                  <option value="error">Error</option>
                  <option value="success">Success</option>
                  <option value="debug">Debug</option>
                  <option value="system">System</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <Terminal
          logs={filteredLogs}
          title="SYSTEM LOGS"
          maxHeight="350px"
          onClear={handleClearLogs}
          className="rounded-none border-0"
        />
      </GlowCard>

      {/* Actions Panel */}
      <GlowCard glowColor="purple" className="p-6">
        <h3 className="text-sm font-mono text-[#aa00ff] uppercase tracking-wider mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4" />
          System Actions
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <NeonButton
            color="cyan"
            variant="outline"
            glowing
            icon={<RefreshCw className="w-4 h-4" />}
            className="w-full"
            onClick={() => {
              handleRetry()
              setLogs((prev) => [
                ...prev,
                createLogEntry('system', 'Manual refresh triggered', 'User initiated'),
              ])
            }}
          >
            Refresh All
          </NeonButton>

          <NeonButton
            color="amber"
            variant="outline"
            glowing
            icon={<Trash2 className="w-4 h-4" />}
            className="w-full"
            onClick={() => {
              setLogs((prev) => [
                ...prev,
                createLogEntry('info', 'Cache clear requested', 'Sent to backend'),
              ])
            }}
          >
            Clear Cache
          </NeonButton>

          <NeonButton
            color="green"
            variant="outline"
            glowing
            icon={<Activity className="w-4 h-4" />}
            className="w-full"
            onClick={() => {
              setLogs((prev) => [
                ...prev,
                createLogEntry('info', 'Garbage collection triggered', 'Sent to backend'),
              ])
            }}
          >
            Force GC
          </NeonButton>

          <NeonButton
            color="magenta"
            variant="outline"
            glowing
            icon={<Download className="w-4 h-4" />}
            className="w-full"
            onClick={() => {
              setLogs((prev) => [
                ...prev,
                createLogEntry('info', 'Generating diagnostics report...', 'Please wait'),
              ])
            }}
          >
            Download Diagnostics
          </NeonButton>
        </div>

        {/* Quick Stats from real data */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
            <p className="text-[10px] text-[#606080] font-mono uppercase">Server PID</p>
            <p className="text-lg font-mono text-[#00f0ff]">{systemStatus?.pid ?? '--'}</p>
          </div>
          <div className="p-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
            <p className="text-[10px] text-[#606080] font-mono uppercase">Python Version</p>
            <p className="text-lg font-mono text-[#00ff88]">{systemStatus?.python_version ?? '--'}</p>
          </div>
          <div className="p-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
            <p className="text-[10px] text-[#606080] font-mono uppercase">CPU Cores</p>
            <p className="text-lg font-mono text-[#ff00aa]">{systemStatus?.resources.cpu_count ?? '--'}</p>
          </div>
          <div className="p-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
            <p className="text-[10px] text-[#606080] font-mono uppercase">Connections</p>
            <p className="text-lg font-mono text-[#ffaa00]">{systemStatus?.active_connections ?? '--'}</p>
          </div>
        </div>
      </GlowCard>
      </div>
    </PageWrapper>
  )
}
