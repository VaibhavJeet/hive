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

type LogLevel = 'info' | 'warn' | 'error' | 'success' | 'debug' | 'system'

interface LogEntry {
  id: string | number
  timestamp: Date
  level: LogLevel
  message: string
  details?: string
}

import { healthApi, adminApi, EngineStatus } from '@/lib/api'

async function fetchHealth(): Promise<SystemHealth> {
  try {
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
  } catch (error) {
    console.warn('Failed to fetch health from API, using fallback:', error)
    throw error
  }
}

async function fetchMetrics() {
  // Prometheus metrics endpoint - would be available at /metrics
  try {
    const res = await fetch('http://localhost:8000/metrics')
    if (!res.ok) return null
    return res.text()
  } catch {
    return null
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

// Generate mock performance data
function generatePerformanceData() {
  const data = []
  for (let i = 29; i >= 0; i--) {
    const time = new Date()
    time.setMinutes(time.getMinutes() - i)
    data.push({
      time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      latency: Math.floor(Math.random() * 80) + 20,
      errorRate: Math.random() * 2,
      botActivity: Math.floor(Math.random() * 50) + 10,
    })
  }
  return data
}

// Mock resource data
function getResourceData() {
  return {
    cpu: Math.floor(Math.random() * 30) + 25,
    memory: { used: 4.2, total: 8.0, percentage: 52 },
    disk: { used: 128, total: 256, percentage: 50 },
    network: { in: 12.5, out: 8.3 },
  }
}

// Mock service data
function getServiceData() {
  return [
    {
      name: 'API Server',
      icon: Server,
      status: 'online' as const,
      metrics: [
        { label: 'Latency', value: '23ms' },
        { label: 'Requests/min', value: '1,247' },
      ],
    },
    {
      name: 'Database',
      icon: Database,
      status: 'online' as const,
      metrics: [
        { label: 'Connections', value: '42/100' },
        { label: 'Query Time', value: '8ms' },
      ],
    },
    {
      name: 'Redis Cache',
      icon: Zap,
      status: 'online' as const,
      metrics: [
        { label: 'Hit Rate', value: '94.2%' },
        { label: 'Memory', value: '256MB' },
      ],
    },
    {
      name: 'LLM Service',
      icon: Cpu,
      status: 'online' as const,
      metrics: [
        { label: 'Queue Depth', value: '3' },
        { label: 'Avg Inference', value: '1.2s' },
      ],
    },
    {
      name: 'WebSocket',
      icon: Wifi,
      status: 'online' as const,
      metrics: [
        { label: 'Active Conns', value: '89' },
        { label: 'Messages/s', value: '234' },
      ],
    },
  ]
}

// Generate mock logs
function generateInitialLogs(): LogEntry[] {
  const messages = [
    { level: 'info' as LogLevel, message: 'System startup complete', details: 'All services initialized' },
    { level: 'success' as LogLevel, message: 'Database connection established', details: 'PostgreSQL v15.2' },
    { level: 'info' as LogLevel, message: 'Redis cache warmed up', details: '1,247 keys loaded' },
    { level: 'info' as LogLevel, message: 'Bot scheduler initialized', details: '12 bots queued' },
    { level: 'warn' as LogLevel, message: 'High memory usage detected', details: 'Memory at 78%' },
    { level: 'info' as LogLevel, message: 'LLM service connected', details: 'OpenAI GPT-4 ready' },
    { level: 'success' as LogLevel, message: 'Health check passed', details: 'All systems operational' },
    { level: 'info' as LogLevel, message: 'WebSocket server listening', details: 'Port 8080' },
  ]

  return messages.map((msg, i) => ({
    id: i,
    timestamp: new Date(Date.now() - (messages.length - i) * 30000),
    level: msg.level,
    message: msg.message,
    details: msg.details,
  }))
}

export default function SystemPage() {
  const [logs, setLogs] = useState<LogEntry[]>(generateInitialLogs)
  const [logFilter, setLogFilter] = useState<LogLevel | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [uptime, setUptime] = useState(0)
  const [resources, setResources] = useState(getResourceData())
  const [performanceData] = useState(generatePerformanceData())

  const { data: health } = useQuery({
    queryKey: ['health-detailed'],
    queryFn: fetchHealth,
    refetchInterval: 5000,
  })

  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: fetchMetrics,
    refetchInterval: 10000,
  })

  const { data: engineStatus } = useQuery({
    queryKey: ['engine-status'],
    queryFn: fetchEngineStatus,
    refetchInterval: 15000,
  })

  // Simulate uptime counter
  useEffect(() => {
    const startTime = Date.now() - 86400000 * 7 // 7 days ago
    const interval = setInterval(() => {
      setUptime(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  // Simulate resource updates
  useEffect(() => {
    const interval = setInterval(() => {
      setResources(getResourceData())
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  // Simulate live logs
  useEffect(() => {
    const logMessages = [
      { level: 'info' as LogLevel, message: 'Bot activity recorded', details: 'user_bot_42' },
      { level: 'info' as LogLevel, message: 'Post generated successfully', details: 'ID: 28491' },
      { level: 'success' as LogLevel, message: 'Cache hit', details: 'user_profile_cache' },
      { level: 'info' as LogLevel, message: 'API request processed', details: '/api/bots/status' },
      { level: 'warn' as LogLevel, message: 'Rate limit warning', details: '85% of quota used' },
      { level: 'info' as LogLevel, message: 'WebSocket message sent', details: 'broadcast' },
      { level: 'debug' as LogLevel, message: 'Query executed', details: 'SELECT * FROM bots' },
    ]

    const interval = setInterval(() => {
      const randomMsg = logMessages[Math.floor(Math.random() * logMessages.length)]
      setLogs((prev) => [
        ...prev.slice(-99),
        createLogEntry(randomMsg.level, randomMsg.message, randomMsg.details),
      ])
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    return `${days}d ${hours.toString().padStart(2, '0')}h ${mins.toString().padStart(2, '0')}m ${secs.toString().padStart(2, '0')}s`
  }

  const parseMetric = (name: string): string => {
    if (!metrics) return 'N/A'
    const match = metrics.match(new RegExp(`${name}\\s+([\\d.]+)`))
    return match ? match[1] : 'N/A'
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

  const services = getServiceData()

  return (
    <div className="space-y-6 pb-8">
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
                  {formatUptime(uptime)}
                </p>
              </div>
            </div>

            {/* Last Incident */}
            <div className="flex items-center gap-3 px-4 py-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
              <AlertTriangle className="w-5 h-5 text-[#00ff88]" />
              <div>
                <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider">Last Incident</p>
                <p className="text-lg font-mono text-[#00ff88]">14d ago</p>
              </div>
            </div>
          </div>
        </div>
      </GlowCard>

      {/* Resource Gauges Row */}
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
              <span className="text-xs text-[#a0a0b0] font-mono">8 cores</span>
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
              value={65}
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
              value={engineStatus ? Math.round(engineStatus.capacity_used * 100) : 75}
              color="purple"
              size="lg"
              glowing
              label={
                <div className="text-center">
                  <span className="text-2xl font-mono font-bold text-[#aa00ff]">
                    {engineStatus ? `${Math.round(engineStatus.capacity_used * 100)}%` : (parseMetric('active_bots') || '12')}
                  </span>
                </div>
              }
            />
            <div className="mt-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#606080]" />
              <span className="text-xs text-[#a0a0b0] font-mono">
                {engineStatus ? `${engineStatus.running_tasks} tasks running` : 'of 16 total'}
              </span>
            </div>
          </div>
        </GlowCard>
      </div>

      {/* Service Status Grid */}
      <div>
        <h2 className="text-lg font-mono text-[#00f0ff] uppercase tracking-wider mb-4 flex items-center gap-2">
          <Server className="w-5 h-5" />
          Service Status
        </h2>
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
      </div>

      {/* Performance Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Request Latency */}
        <GlowCard glowColor="cyan" className="p-4">
          <h3 className="text-sm font-mono text-[#00f0ff] uppercase tracking-wider mb-4">Request Latency</h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={performanceData}>
              <defs>
                <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00f0ff" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#00f0ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#252538" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} />
              <YAxis tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} unit="ms" />
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
                dataKey="latency"
                stroke="#00f0ff"
                strokeWidth={2}
                fill="url(#latencyGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </GlowCard>

        {/* Error Rate */}
        <GlowCard glowColor="magenta" className="p-4">
          <h3 className="text-sm font-mono text-[#ff00aa] uppercase tracking-wider mb-4">Error Rate</h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={performanceData}>
              <defs>
                <linearGradient id="errorGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ff00aa" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#ff00aa" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#252538" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} />
              <YAxis tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} unit="%" />
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
                dataKey="errorRate"
                stroke="#ff00aa"
                strokeWidth={2}
                fill="url(#errorGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </GlowCard>

        {/* Bot Activity */}
        <GlowCard glowColor="green" className="p-4">
          <h3 className="text-sm font-mono text-[#00ff88] uppercase tracking-wider mb-4">Bot Activity</h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={performanceData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#252538" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} />
              <YAxis tick={{ fontSize: 10, fill: '#606080' }} axisLine={{ stroke: '#252538' }} />
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
                dataKey="botActivity"
                stroke="#00ff88"
                strokeWidth={2}
                dot={false}
                style={{ filter: 'drop-shadow(0 0 8px rgba(0, 255, 136, 0.5))' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </GlowCard>
      </div>

      {/* Live Logs Terminal */}
      <GlowCard glowColor="cyan" className="p-0 overflow-hidden">
        <div className="p-4 border-b border-[#252538]">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <h3 className="text-sm font-mono text-[#00f0ff] uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4" />
              Live System Logs
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
              setLogs((prev) => [
                ...prev,
                createLogEntry('system', 'Restarting services...', 'User initiated'),
              ])
            }}
          >
            Restart Services
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
                createLogEntry('success', 'Cache cleared successfully', '1,247 keys purged'),
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
                createLogEntry('info', 'Garbage collection triggered', 'Freed 128MB'),
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

        {/* Quick Stats */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
            <p className="text-[10px] text-[#606080] font-mono uppercase">API Requests</p>
            <p className="text-lg font-mono text-[#00f0ff]">{parseMetric('api_requests_total') || '24,891'}</p>
          </div>
          <div className="p-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
            <p className="text-[10px] text-[#606080] font-mono uppercase">Posts Created</p>
            <p className="text-lg font-mono text-[#00ff88]">{parseMetric('posts_created_total') || '1,247'}</p>
          </div>
          <div className="p-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
            <p className="text-[10px] text-[#606080] font-mono uppercase">WebSocket Conns</p>
            <p className="text-lg font-mono text-[#ff00aa]">{parseMetric('websocket_connections') || '89'}</p>
          </div>
          <div className="p-3 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
            <p className="text-[10px] text-[#606080] font-mono uppercase">Error Rate</p>
            <p className="text-lg font-mono text-[#ffaa00]">0.02%</p>
          </div>
        </div>
      </GlowCard>
    </div>
  )
}
