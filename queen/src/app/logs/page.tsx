'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  Search,
  Filter,
  Pause,
  Play,
  Trash2,
  X,
  Copy,
  Check,
  ChevronRight,
  AlertTriangle,
  AlertCircle,
  Info,
  Bug,
  Wifi,
  Server,
  Database,
  Cpu,
  Clock,
  Activity,
  Zap,
  ExternalLink,
  RefreshCw,
} from 'lucide-react'
import { GlowCard } from '@/components/ui/GlowCard'
import { NeonButton } from '@/components/ui/NeonButton'

// Types
type LogLevel = 'info' | 'warning' | 'error' | 'debug'
type ServiceType = 'API' | 'Database' | 'LLM' | 'WebSocket' | 'Scheduler'

interface LogEntry {
  id: string
  timestamp: Date
  level: LogLevel
  service: ServiceType
  message: string
  details?: string
  stackTrace?: string
  requestData?: object
  responseData?: object
  relatedLogs?: string[]
  duration?: number
}

// Level configuration
const levelConfig: Record<LogLevel, { color: string; bg: string; icon: typeof Info; label: string }> = {
  info: {
    color: '#00f0ff',
    bg: 'rgba(0, 240, 255, 0.15)',
    icon: Info,
    label: 'INFO',
  },
  warning: {
    color: '#ffaa00',
    bg: 'rgba(255, 170, 0, 0.15)',
    icon: AlertTriangle,
    label: 'WARN',
  },
  error: {
    color: '#ff0044',
    bg: 'rgba(255, 0, 68, 0.15)',
    icon: AlertCircle,
    label: 'ERROR',
  },
  debug: {
    color: '#a0a0b0',
    bg: 'rgba(160, 160, 176, 0.15)',
    icon: Bug,
    label: 'DEBUG',
  },
}

// Service configuration
const serviceConfig: Record<ServiceType, { color: string; icon: typeof Server }> = {
  API: { color: '#00f0ff', icon: Server },
  Database: { color: '#00ff88', icon: Database },
  LLM: { color: '#aa00ff', icon: Cpu },
  WebSocket: { color: '#ff00aa', icon: Wifi },
  Scheduler: { color: '#ffaa00', icon: Clock },
}

// Generate mock logs
function generateMockLogs(count: number): LogEntry[] {
  const messages: Array<{ level: LogLevel; service: ServiceType; message: string; details?: string }> = [
    { level: 'info', service: 'API', message: 'Request processed successfully', details: 'GET /api/bots/status - 200 OK' },
    { level: 'info', service: 'API', message: 'User authenticated', details: 'user_id: usr_12345' },
    { level: 'info', service: 'Database', message: 'Query executed', details: 'SELECT * FROM bots WHERE status = active' },
    { level: 'info', service: 'Database', message: 'Connection pool healthy', details: '42/100 connections active' },
    { level: 'info', service: 'LLM', message: 'Inference completed', details: 'Model: gpt-4, Tokens: 1,247' },
    { level: 'info', service: 'LLM', message: 'Response generated', details: 'bot_id: bot_quantum_mind' },
    { level: 'info', service: 'WebSocket', message: 'Client connected', details: 'session_id: ws_89234' },
    { level: 'info', service: 'WebSocket', message: 'Message broadcast', details: '89 active clients' },
    { level: 'info', service: 'Scheduler', message: 'Job completed', details: 'bot_activity_scheduler' },
    { level: 'info', service: 'Scheduler', message: 'Next run scheduled', details: 'in 5 minutes' },
    { level: 'warning', service: 'API', message: 'Rate limit warning', details: '85% of quota used for IP 192.168.1.100' },
    { level: 'warning', service: 'API', message: 'Slow response detected', details: 'Endpoint /api/analytics took 2.3s' },
    { level: 'warning', service: 'Database', message: 'High query time', details: 'Query took 450ms (threshold: 200ms)' },
    { level: 'warning', service: 'LLM', message: 'Token limit approaching', details: '92% of daily quota consumed' },
    { level: 'warning', service: 'WebSocket', message: 'Connection unstable', details: 'client_id: ws_45678, latency: 850ms' },
    { level: 'warning', service: 'Scheduler', message: 'Job delayed', details: 'Queue depth: 15 jobs pending' },
    { level: 'error', service: 'API', message: 'Request failed', details: 'POST /api/posts - 500 Internal Server Error' },
    { level: 'error', service: 'Database', message: 'Connection timeout', details: 'Unable to reach database after 30s' },
    { level: 'error', service: 'LLM', message: 'Inference failed', details: 'Model overloaded, retry in 60s' },
    { level: 'error', service: 'WebSocket', message: 'Client disconnected unexpectedly', details: 'session_id: ws_12345' },
    { level: 'debug', service: 'API', message: 'Request headers received', details: 'Content-Type: application/json' },
    { level: 'debug', service: 'Database', message: 'Query plan optimized', details: 'Using index idx_bots_status' },
    { level: 'debug', service: 'LLM', message: 'Prompt constructed', details: 'Character count: 2,456' },
    { level: 'debug', service: 'Scheduler', message: 'Job queued', details: 'Priority: normal' },
  ]

  const logs: LogEntry[] = []
  for (let i = 0; i < count; i++) {
    const msg = messages[Math.floor(Math.random() * messages.length)]
    const timestamp = new Date(Date.now() - (count - i) * 30000 - Math.random() * 10000)
    logs.push({
      id: `log_${Date.now()}_${i}`,
      timestamp,
      level: msg.level,
      service: msg.service,
      message: msg.message,
      details: msg.details,
      duration: Math.floor(Math.random() * 500) + 10,
      stackTrace: msg.level === 'error' ? `Error: ${msg.message}\n    at processRequest (/app/src/api/handler.ts:142:15)\n    at async Router.handle (/app/src/router/index.ts:89:23)\n    at async Server.handleRequest (/app/src/server.ts:56:12)` : undefined,
      requestData: msg.level !== 'debug' ? { method: 'GET', path: '/api/bots', headers: { 'Content-Type': 'application/json' } } : undefined,
      responseData: msg.level !== 'debug' ? { status: msg.level === 'error' ? 500 : 200, body: { success: msg.level !== 'error' } } : undefined,
    })
  }
  return logs
}

// JSON Syntax Highlighter Component
function JsonHighlight({ data }: { data: object }) {
  const json = JSON.stringify(data, null, 2)
  const highlighted = json
    .replace(/"([^"]+)":/g, '<span style="color: #aa00ff">"$1"</span>:')
    .replace(/: "([^"]+)"/g, ': <span style="color: #00ff88">"$1"</span>')
    .replace(/: (\d+)/g, ': <span style="color: #00f0ff">$1</span>')
    .replace(/: (true|false)/g, ': <span style="color: #ffaa00">$1</span>')

  return (
    <pre
      className="text-xs font-mono text-[#a0a0b0] overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  )
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>(() => generateMockLogs(50))
  const [levelFilter, setLevelFilter] = useState<LogLevel | 'all'>('all')
  const [serviceFilter, setServiceFilter] = useState<ServiceType | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const [isStreaming, setIsStreaming] = useState(true)
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)
  const [copied, setCopied] = useState(false)
  const [newLogIds, setNewLogIds] = useState<Set<string>>(new Set())
  const scrollRef = useRef<HTMLDivElement>(null)

  // Stats calculation - for simplicity, just use all logs as "last 24h" for the demo
  const stats = useMemo(() => {
    return {
      total: logs.length,
      errors: logs.filter(l => l.level === 'error').length,
      warnings: logs.filter(l => l.level === 'warning').length,
      avgResponseTime: Math.round(logs.reduce((acc, l) => acc + (l.duration || 0), 0) / logs.length) || 0,
    }
  }, [logs])

  // Filtered logs
  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      const matchesLevel = levelFilter === 'all' || log.level === levelFilter
      const matchesService = serviceFilter === 'all' || log.service === serviceFilter
      const matchesSearch = searchQuery === '' ||
        log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (log.details?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false)
      return matchesLevel && matchesService && matchesSearch
    })
  }, [logs, levelFilter, serviceFilter, searchQuery])

  // Auto-scroll effect
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [filteredLogs, autoScroll])

  // Simulate live log streaming
  useEffect(() => {
    if (!isStreaming) return

    const messages: Array<{ level: LogLevel; service: ServiceType; message: string; details?: string }> = [
      { level: 'info', service: 'API', message: 'Request processed', details: 'GET /api/health - 200 OK' },
      { level: 'info', service: 'Database', message: 'Query executed', details: 'Execution time: 12ms' },
      { level: 'info', service: 'WebSocket', message: 'Message delivered', details: 'broadcast to 89 clients' },
      { level: 'warning', service: 'LLM', message: 'High latency detected', details: 'Response time: 1.8s' },
      { level: 'info', service: 'Scheduler', message: 'Task completed', details: 'bot_activity_check' },
      { level: 'debug', service: 'API', message: 'Cache hit', details: 'Key: user_profile_12345' },
      { level: 'info', service: 'LLM', message: 'Inference completed', details: 'Tokens: 892' },
    ]

    const interval = setInterval(() => {
      const msg = messages[Math.floor(Math.random() * messages.length)]
      const newLog: LogEntry = {
        id: `log_${Date.now()}_${Math.random()}`,
        timestamp: new Date(),
        level: msg.level,
        service: msg.service,
        message: msg.message,
        details: msg.details,
        duration: Math.floor(Math.random() * 300) + 20,
      }

      setLogs(prev => [...prev.slice(-199), newLog])
      setNewLogIds(prev => {
        const newSet = new Set(prev)
        newSet.add(newLog.id)
        setTimeout(() => {
          setNewLogIds(p => {
            const updated = new Set(p)
            updated.delete(newLog.id)
            return updated
          })
        }, 2000)
        return newSet
      })
    }, 1500 + Math.random() * 1000)

    return () => clearInterval(interval)
  }, [isStreaming])

  const handleClear = useCallback(() => {
    setLogs([])
    setSelectedLog(null)
  }, [])

  const handleCopyLog = useCallback((log: LogEntry) => {
    const text = JSON.stringify(log, null, 2)
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [])

  const formatTime = (date: Date) => {
    const time = date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
    const ms = date.getMilliseconds().toString().padStart(3, '0')
    return `${time}.${ms}`
  }

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-mono text-[#00f0ff] uppercase tracking-wider flex items-center gap-3"
            style={{ textShadow: '0 0 20px rgba(0, 240, 255, 0.5)' }}
          >
            <Activity className="w-7 h-7" />
            System Logs
          </h1>
          <p className="text-sm text-[#606080] font-mono mt-1">Real-time log monitoring and analysis</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Live indicator */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${isStreaming ? 'border-[#00ff88]/30 bg-[#00ff88]/10' : 'border-[#606080]/30 bg-[#606080]/10'}`}>
            <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-[#00ff88] animate-pulse' : 'bg-[#606080]'}`} />
            <span className={`text-xs font-mono uppercase ${isStreaming ? 'text-[#00ff88]' : 'text-[#606080]'}`}>
              {isStreaming ? 'Live' : 'Paused'}
            </span>
          </div>

          {/* Pause/Resume */}
          <NeonButton
            color={isStreaming ? 'amber' : 'green'}
            variant="outline"
            size="sm"
            icon={isStreaming ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            onClick={() => setIsStreaming(!isStreaming)}
          >
            {isStreaming ? 'Pause' : 'Resume'}
          </NeonButton>

          {/* Auto-scroll toggle */}
          <NeonButton
            color={autoScroll ? 'cyan' : 'purple'}
            variant={autoScroll ? 'solid' : 'outline'}
            size="sm"
            onClick={() => setAutoScroll(!autoScroll)}
          >
            Auto-scroll: {autoScroll ? 'ON' : 'OFF'}
          </NeonButton>

          {/* Clear */}
          <NeonButton
            color="red"
            variant="outline"
            size="sm"
            icon={<Trash2 className="w-4 h-4" />}
            onClick={handleClear}
          >
            Clear
          </NeonButton>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlowCard glowColor="cyan" className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-[#00f0ff]/10">
              <Activity className="w-5 h-5 text-[#00f0ff]" />
            </div>
            <div>
              <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider">Total Logs (24h)</p>
              <p className="text-xl font-mono font-bold text-[#00f0ff]" style={{ textShadow: '0 0 10px rgba(0, 240, 255, 0.5)' }}>
                {stats.total.toLocaleString()}
              </p>
            </div>
          </div>
        </GlowCard>

        <GlowCard glowColor="magenta" className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-[#ff0044]/10">
              <AlertCircle className="w-5 h-5 text-[#ff0044]" />
            </div>
            <div>
              <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider">Errors</p>
              <p className="text-xl font-mono font-bold text-[#ff0044]" style={{ textShadow: '0 0 10px rgba(255, 0, 68, 0.5)' }}>
                {stats.errors}
              </p>
            </div>
          </div>
        </GlowCard>

        <GlowCard glowColor="amber" className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-[#ffaa00]/10">
              <AlertTriangle className="w-5 h-5 text-[#ffaa00]" />
            </div>
            <div>
              <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider">Warnings</p>
              <p className="text-xl font-mono font-bold text-[#ffaa00]" style={{ textShadow: '0 0 10px rgba(255, 170, 0, 0.5)' }}>
                {stats.warnings}
              </p>
            </div>
          </div>
        </GlowCard>

        <GlowCard glowColor="green" className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-[#00ff88]/10">
              <Zap className="w-5 h-5 text-[#00ff88]" />
            </div>
            <div>
              <p className="text-[10px] text-[#606080] font-mono uppercase tracking-wider">Avg Response Time</p>
              <p className="text-xl font-mono font-bold text-[#00ff88]" style={{ textShadow: '0 0 10px rgba(0, 255, 136, 0.5)' }}>
                {stats.avgResponseTime}ms
              </p>
            </div>
          </div>
        </GlowCard>
      </div>

      {/* Filters Row */}
      <GlowCard glowColor="purple" className="p-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#606080]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search logs..."
              className="w-full pl-10 pr-4 py-2 bg-[#1a1a2e] border border-[#252538] rounded-lg text-sm font-mono text-[#e0e0e0] placeholder-[#606080] focus:outline-none focus:border-[#00f0ff] transition-colors"
            />
          </div>

          {/* Level filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-[#606080]" />
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value as LogLevel | 'all')}
              className="bg-[#1a1a2e] border border-[#252538] rounded-lg text-sm font-mono text-[#e0e0e0] px-3 py-2 focus:outline-none focus:border-[#00f0ff] cursor-pointer"
            >
              <option value="all">All Levels</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="debug">Debug</option>
            </select>
          </div>

          {/* Service filter */}
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-[#606080]" />
            <select
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value as ServiceType | 'all')}
              className="bg-[#1a1a2e] border border-[#252538] rounded-lg text-sm font-mono text-[#e0e0e0] px-3 py-2 focus:outline-none focus:border-[#00f0ff] cursor-pointer"
            >
              <option value="all">All Services</option>
              <option value="API">API</option>
              <option value="Database">Database</option>
              <option value="LLM">LLM</option>
              <option value="WebSocket">WebSocket</option>
              <option value="Scheduler">Scheduler</option>
            </select>
          </div>

          {/* Quick filters */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setLevelFilter('error'); setServiceFilter('all'); }}
              className="px-3 py-1.5 text-xs font-mono uppercase bg-[#ff0044]/10 text-[#ff0044] rounded-lg border border-[#ff0044]/30 hover:bg-[#ff0044]/20 transition-colors"
            >
              Errors Only
            </button>
            <button
              onClick={() => { setLevelFilter('all'); setServiceFilter('all'); setSearchQuery(''); }}
              className="px-3 py-1.5 text-xs font-mono uppercase bg-[#606080]/10 text-[#606080] rounded-lg border border-[#606080]/30 hover:bg-[#606080]/20 transition-colors"
            >
              Reset
            </button>
          </div>
        </div>
      </GlowCard>

      {/* Main Content - Log Viewer + Detail Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Log Viewer (Terminal Style) */}
        <div className={`${selectedLog ? 'lg:col-span-2' : 'lg:col-span-3'}`}>
          <div className="rounded-xl overflow-hidden bg-[#0a0a0f] border border-[#252538]">
            {/* Terminal Header */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-[#12121a] border-b border-[#252538]">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-[#ff0044]" />
                  <span className="w-3 h-3 rounded-full bg-[#ffaa00]" />
                  <span className="w-3 h-3 rounded-full bg-[#00ff88]" />
                </div>
                <span className="text-[#00f0ff] text-xs uppercase tracking-wider font-mono">
                  System Logs Terminal
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono text-[#606080]">
                  {filteredLogs.length} entries
                </span>
                {isStreaming && (
                  <span className="flex items-center gap-1.5 text-[#00ff88] text-xs font-mono">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#00ff88] animate-pulse" />
                    LIVE
                  </span>
                )}
              </div>
            </div>

            {/* Log Content */}
            <div
              ref={scrollRef}
              className="overflow-auto font-mono text-sm"
              style={{ maxHeight: '600px' }}
            >
              {filteredLogs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-[#606080]">
                  <Activity className="w-12 h-12 mb-4 opacity-30" />
                  <p className="text-sm">No logs to display</p>
                  <p className="text-xs mt-1">Waiting for log entries...</p>
                </div>
              ) : (
                <div className="p-2">
                  {filteredLogs.map((log) => {
                    const levelConf = levelConfig[log.level]
                    const serviceConf = serviceConfig[log.service]
                    const LevelIcon = levelConf.icon
                    const isNew = newLogIds.has(log.id)
                    const isSelected = selectedLog?.id === log.id

                    return (
                      <div
                        key={log.id}
                        onClick={() => setSelectedLog(log)}
                        className={`
                          flex items-start gap-2 px-2 py-1.5 rounded cursor-pointer
                          transition-all duration-300
                          ${isNew ? 'bg-[#00f0ff]/10 animate-pulse' : 'hover:bg-white/[0.03]'}
                          ${isSelected ? 'bg-[#00f0ff]/20 border-l-2 border-[#00f0ff]' : ''}
                        `}
                      >
                        {/* Timestamp */}
                        <span className="text-[#00f0ff] text-xs flex-shrink-0 w-24">
                          [{formatTime(log.timestamp)}]
                        </span>

                        {/* Level Badge */}
                        <span
                          className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 w-16 justify-center"
                          style={{
                            color: levelConf.color,
                            backgroundColor: levelConf.bg,
                          }}
                        >
                          <LevelIcon className="w-3 h-3" />
                          {levelConf.label}
                        </span>

                        {/* Service Tag */}
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 w-20 text-center"
                          style={{
                            color: serviceConf.color,
                            backgroundColor: `${serviceConf.color}20`,
                          }}
                        >
                          {log.service}
                        </span>

                        {/* Message */}
                        <span className="text-[#e0e0e0] flex-1 truncate">
                          {log.message}
                          {log.details && (
                            <span className="text-[#606080] ml-2">{log.details}</span>
                          )}
                        </span>

                        {/* Duration */}
                        {log.duration && (
                          <span className="text-[10px] text-[#606080] flex-shrink-0">
                            {log.duration}ms
                          </span>
                        )}

                        {/* Expand indicator */}
                        <ChevronRight className={`w-4 h-4 text-[#606080] flex-shrink-0 transition-transform ${isSelected ? 'rotate-90 text-[#00f0ff]' : ''}`} />
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Status Bar */}
            <div className="flex items-center justify-between px-4 py-2 bg-[#12121a] border-t border-[#252538] text-[10px] font-mono">
              <div className="flex items-center gap-4">
                <span className="text-[#606080]">
                  Showing {filteredLogs.length} of {logs.length}
                </span>
                {searchQuery && (
                  <span className="text-[#aa00ff]">
                    Filter: &quot;{searchQuery}&quot;
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4">
                <span className="text-[#606080]">
                  SCROLL: {autoScroll ? 'AUTO' : 'MANUAL'}
                </span>
                <span className="text-[#00f0ff]">
                  STREAM: {isStreaming ? 'ACTIVE' : 'PAUSED'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Log Detail Panel */}
        {selectedLog && (
          <div className="lg:col-span-1">
            <GlowCard glowColor="cyan" className="p-0 overflow-hidden sticky top-6">
              {/* Panel Header */}
              <div className="flex items-center justify-between p-4 border-b border-[#252538]">
                <h3 className="text-sm font-mono text-[#00f0ff] uppercase tracking-wider">
                  Log Details
                </h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCopyLog(selectedLog)}
                    className="p-1.5 rounded-lg hover:bg-white/10 text-[#606080] hover:text-[#00f0ff] transition-colors"
                    title="Copy log entry"
                  >
                    {copied ? <Check className="w-4 h-4 text-[#00ff88]" /> : <Copy className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => setSelectedLog(null)}
                    className="p-1.5 rounded-lg hover:bg-white/10 text-[#606080] hover:text-[#ff0044] transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Panel Content */}
              <div className="p-4 space-y-4 max-h-[calc(600px-60px)] overflow-y-auto">
                {/* Timestamp */}
                <div>
                  <p className="text-[10px] text-[#606080] font-mono uppercase mb-1">Timestamp</p>
                  <p className="text-sm font-mono text-[#00f0ff]">
                    {formatDate(selectedLog.timestamp)} {formatTime(selectedLog.timestamp)}
                  </p>
                </div>

                {/* Level & Service */}
                <div className="flex gap-4">
                  <div>
                    <p className="text-[10px] text-[#606080] font-mono uppercase mb-1">Level</p>
                    <span
                      className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-mono"
                      style={{
                        color: levelConfig[selectedLog.level].color,
                        backgroundColor: levelConfig[selectedLog.level].bg,
                      }}
                    >
                      {(() => {
                        const Icon = levelConfig[selectedLog.level].icon
                        return <Icon className="w-3.5 h-3.5" />
                      })()}
                      {levelConfig[selectedLog.level].label}
                    </span>
                  </div>
                  <div>
                    <p className="text-[10px] text-[#606080] font-mono uppercase mb-1">Service</p>
                    <span
                      className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-mono"
                      style={{
                        color: serviceConfig[selectedLog.service].color,
                        backgroundColor: `${serviceConfig[selectedLog.service].color}20`,
                      }}
                    >
                      {(() => {
                        const Icon = serviceConfig[selectedLog.service].icon
                        return <Icon className="w-3.5 h-3.5" />
                      })()}
                      {selectedLog.service}
                    </span>
                  </div>
                </div>

                {/* Message */}
                <div>
                  <p className="text-[10px] text-[#606080] font-mono uppercase mb-1">Message</p>
                  <p className="text-sm font-mono text-[#e0e0e0] bg-[#1a1a2e] p-2 rounded-lg">
                    {selectedLog.message}
                  </p>
                </div>

                {/* Details */}
                {selectedLog.details && (
                  <div>
                    <p className="text-[10px] text-[#606080] font-mono uppercase mb-1">Details</p>
                    <p className="text-sm font-mono text-[#a0a0b0] bg-[#1a1a2e] p-2 rounded-lg">
                      {selectedLog.details}
                    </p>
                  </div>
                )}

                {/* Duration */}
                {selectedLog.duration && (
                  <div>
                    <p className="text-[10px] text-[#606080] font-mono uppercase mb-1">Duration</p>
                    <p className="text-sm font-mono text-[#00ff88]">{selectedLog.duration}ms</p>
                  </div>
                )}

                {/* Stack Trace */}
                {selectedLog.stackTrace && (
                  <div>
                    <p className="text-[10px] text-[#606080] font-mono uppercase mb-1 flex items-center gap-2">
                      Stack Trace
                      <span className="text-[#ff0044]">ERROR</span>
                    </p>
                    <pre className="text-xs font-mono text-[#ff0044] bg-[#1a1a2e] p-3 rounded-lg overflow-x-auto whitespace-pre-wrap">
                      {selectedLog.stackTrace}
                    </pre>
                  </div>
                )}

                {/* Request Data */}
                {selectedLog.requestData && (
                  <div>
                    <p className="text-[10px] text-[#606080] font-mono uppercase mb-1">Request Data</p>
                    <div className="bg-[#1a1a2e] p-3 rounded-lg">
                      <JsonHighlight data={selectedLog.requestData} />
                    </div>
                  </div>
                )}

                {/* Response Data */}
                {selectedLog.responseData && (
                  <div>
                    <p className="text-[10px] text-[#606080] font-mono uppercase mb-1">Response Data</p>
                    <div className="bg-[#1a1a2e] p-3 rounded-lg">
                      <JsonHighlight data={selectedLog.responseData} />
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="pt-2 border-t border-[#252538]">
                  <p className="text-[10px] text-[#606080] font-mono uppercase mb-2">Actions</p>
                  <div className="flex flex-wrap gap-2">
                    <button className="flex items-center gap-1.5 px-2 py-1 text-xs font-mono text-[#606080] hover:text-[#00f0ff] bg-[#1a1a2e] rounded-lg hover:bg-[#1a1a2e]/80 transition-colors">
                      <RefreshCw className="w-3 h-3" />
                      Find Related
                    </button>
                    <button className="flex items-center gap-1.5 px-2 py-1 text-xs font-mono text-[#606080] hover:text-[#00f0ff] bg-[#1a1a2e] rounded-lg hover:bg-[#1a1a2e]/80 transition-colors">
                      <ExternalLink className="w-3 h-3" />
                      Open in New Tab
                    </button>
                  </div>
                </div>
              </div>
            </GlowCard>
          </div>
        )}
      </div>
    </div>
  )
}
