'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3'
import { API_BASE_URL } from '@/lib/api'
import { getWebSocketManager, EventHandlers } from '@/lib/websocket'

// ============================================================================
// Types
// ============================================================================

interface WorldMapBot {
  id: string
  name: string
  handle: string
  avatar_seed: string
  community_ids: string[]
  life_stage: string
  vitality: number
  is_alive: boolean
  generation: number
  interests: string[]
  mood: string
  connections: { target_id: string; affinity: number; type: string }[]
}

interface WorldMapCommunity {
  id: string
  name: string
  theme: string
  tone: string
  member_count: number
  activity_level: number
  topics: string[]
}

interface WorldMapData {
  communities: WorldMapCommunity[]
  bots: WorldMapBot[]
  era: string
  living_count: number
  departed_count: number
  generations: number
}

// D3 simulation node types
interface CommunityNode extends d3.SimulationNodeDatum {
  id: string
  type: 'community'
  data: WorldMapCommunity
  radius: number
  color: string
}

interface BotNode extends d3.SimulationNodeDatum {
  id: string
  type: 'bot'
  data: WorldMapBot
  communityId: string | null
  radius: number
  color: string
}

type SimNode = CommunityNode | BotNode

interface SimLink extends d3.SimulationLinkDatum<BotNode> {
  affinity: number
  type: string
}

// ============================================================================
// Color scheme — community theme to color mapping
// ============================================================================

// Vibrant color palette — each community gets a distinct saturated color
const COMMUNITY_PALETTE = [
  '#00f0ff', // electric cyan
  '#ff3366', // hot pink
  '#44ff88', // neon green
  '#ffaa00', // amber
  '#aa55ff', // violet
  '#ff6633', // tangerine
  '#33ddff', // sky blue
  '#ff44cc', // magenta
  '#88ff44', // lime
  '#ffdd33', // gold
  '#6644ff', // indigo
  '#ff8855', // coral
  '#33ffcc', // turquoise
  '#ff3399', // rose
  '#44ccff', // cerulean
]

const THEME_COLORS: Record<string, string> = {
  technology: '#00f0ff',
  programming: '#44ff88',
  art: '#ff3366',
  music: '#ffaa00',
  science: '#33ddff',
  philosophy: '#aa55ff',
  gaming: '#ff6633',
  literature: '#44ccff',
  wellness: '#33ffcc',
  food: '#ffdd33',
  sports: '#ff8855',
  fashion: '#ff44cc',
  photography: '#6644ff',
  film: '#ff3399',
  travel: '#88ff44',
  default: '#888899',
}

// Assign colors to communities by index (fallback if theme doesn't match)
let _communityColorIndex = 0
const _communityColorCache: Record<string, string> = {}

function getCommunityColor(communityId: string, theme: string): string {
  if (_communityColorCache[communityId]) return _communityColorCache[communityId]

  // Try theme-based color first
  const key = theme.toLowerCase()
  for (const [pattern, color] of Object.entries(THEME_COLORS)) {
    if (pattern !== 'default' && key.includes(pattern)) {
      _communityColorCache[communityId] = color
      return color
    }
  }

  // Fall back to palette by index (ensures distinct colors)
  const color = COMMUNITY_PALETTE[_communityColorIndex % COMMUNITY_PALETTE.length]
  _communityColorIndex++
  _communityColorCache[communityId] = color
  return color
}

const LIFE_STAGE_RADIUS: Record<string, number> = {
  young: 4,
  mature: 8,
  elder: 13,
  ancient: 18,
}

// Visual ring for elder+ bots (wisdom indicator)
const LIFE_STAGE_RING: Record<string, boolean> = {
  young: false,
  mature: false,
  elder: true,
  ancient: true,
}

const MOOD_GLOW: Record<string, string> = {
  joyful: '#44ff88',
  content: '#88ddff',
  excited: '#ffaa00',
  anxious: '#ff8844',
  melancholic: '#aa88ff',
  neutral: '#556677',
}

// ============================================================================
// Asteroid / Comet animation
// ============================================================================

interface AsteroidConfig {
  sourceId: string
  targetId: string
  color: string
  label?: string  // e.g. "liked", "commented"
}

function launchAsteroid(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  sourceNode: { x: number; y: number },
  targetNode: { x: number; y: number },
  color: string,
  label?: string
) {
  if (!sourceNode?.x || !targetNode?.x) return

  const sx = sourceNode.x, sy = sourceNode.y
  const tx = targetNode.x, ty = targetNode.y

  // Compute a curved arc — control point offset perpendicular to the line
  const dx = tx - sx, dy = ty - sy
  const dist = Math.sqrt(dx * dx + dy * dy)
  const curvature = 0.35 + Math.random() * 0.15 // Slight randomness
  const sign = Math.random() > 0.5 ? 1 : -1     // Curve left or right randomly
  const cx = (sx + tx) / 2 + (-dy) * curvature * sign
  const cy = (sy + ty) / 2 + (dx) * curvature * sign

  const arcPath = `M ${sx},${sy} Q ${cx},${cy} ${tx},${ty}`
  const duration = Math.max(600, Math.min(1200, dist * 3))

  const asteroid = g.append('g').attr('class', 'asteroid')

  // SVG defs for glow filter (scoped to this asteroid)
  const filterId = `glow-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
  const defs = asteroid.append('defs')
  const filter = defs.append('filter').attr('id', filterId)
  filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur')
  const merge = filter.append('feMerge')
  merge.append('feMergeNode').attr('in', 'blur')
  merge.append('feMergeNode').attr('in', 'SourceGraphic')

  // Glowing arc trail — draws behind the comet
  const trail = asteroid.append('path')
    .attr('d', arcPath)
    .attr('fill', 'none')
    .attr('stroke', color)
    .attr('stroke-width', 2.5)
    .attr('stroke-opacity', 0.6)
    .attr('stroke-linecap', 'round')
    .attr('filter', `url(#${filterId})`)

  // Animate trail drawing using stroke-dasharray
  const pathNode = trail.node() as SVGPathElement
  if (pathNode) {
    const totalLength = pathNode.getTotalLength()
    trail
      .attr('stroke-dasharray', `${totalLength} ${totalLength}`)
      .attr('stroke-dashoffset', totalLength)
      .transition()
      .duration(duration)
      .ease(d3.easeQuadOut)
      .attr('stroke-dashoffset', 0)

    // Fade the trail out after drawing
    trail.transition()
      .delay(duration)
      .duration(400)
      .attr('stroke-opacity', 0)
      .remove()

    // Comet head — animate along the arc path
    const head = asteroid.append('circle')
      .attr('r', 4)
      .attr('fill', color)
      .attr('filter', `url(#${filterId})`)

    // Outer glow head
    const headGlow = asteroid.append('circle')
      .attr('r', 8)
      .attr('fill', color)
      .attr('fill-opacity', 0.25)

    // Custom tween to move along the path
    head.transition()
      .duration(duration)
      .ease(d3.easeQuadOut)
      .attrTween('cx', () => {
        return (t: number) => {
          const p = pathNode.getPointAtLength(t * totalLength)
          return String(p.x)
        }
      })
      .attrTween('cy', () => {
        return (t: number) => {
          const p = pathNode.getPointAtLength(t * totalLength)
          return String(p.y)
        }
      })

    headGlow.transition()
      .duration(duration)
      .ease(d3.easeQuadOut)
      .attrTween('cx', () => {
        return (t: number) => {
          const p = pathNode.getPointAtLength(t * totalLength)
          return String(p.x)
        }
      })
      .attrTween('cy', () => {
        return (t: number) => {
          const p = pathNode.getPointAtLength(t * totalLength)
          return String(p.y)
        }
      })
      .attr('fill-opacity', 0)
  }

  // Impact burst at destination
  setTimeout(() => {
    // Expanding ring
    g.append('circle')
      .attr('cx', tx).attr('cy', ty)
      .attr('r', 4)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.8)
      .transition().duration(600).ease(d3.easeExpOut)
      .attr('r', 24)
      .attr('stroke-opacity', 0)
      .remove()

    // Second ring (staggered)
    g.append('circle')
      .attr('cx', tx).attr('cy', ty)
      .attr('r', 3)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.5)
      .transition().delay(100).duration(500).ease(d3.easeExpOut)
      .attr('r', 16)
      .attr('stroke-opacity', 0)
      .remove()

    // Clean up asteroid group
    asteroid.transition().delay(500).remove()
  }, duration)
}

// Pulse effect on a bot node
function pulseBot(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  node: { x: number; y: number },
  color: string
) {
  if (!node?.x) return

  const ring = g.append('circle')
    .attr('cx', node.x)
    .attr('cy', node.y)
    .attr('r', 5)
    .attr('fill', 'none')
    .attr('stroke', color)
    .attr('stroke-width', 1.5)
    .attr('stroke-opacity', 0.7)

  ring.transition()
    .duration(1000)
    .ease(d3.easeExpOut)
    .attr('r', 25)
    .attr('stroke-opacity', 0)
    .remove()
}

// Evolution animation — spiral rings + upward particles (DNA-like)
function evolveBot(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  node: { x: number; y: number },
  color: string
) {
  if (!node?.x) return

  const nx = node.x, ny = node.y

  // Spinning rings expanding outward (like a level-up aura)
  for (let i = 0; i < 3; i++) {
    g.append('circle')
      .attr('cx', nx).attr('cy', ny)
      .attr('r', 6)
      .attr('fill', 'none')
      .attr('stroke', i === 1 ? '#ffffff' : color)
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.7)
      .attr('stroke-dasharray', '4,4')
      .transition()
      .delay(i * 150)
      .duration(1000)
      .ease(d3.easeExpOut)
      .attr('r', 30 + i * 8)
      .attr('stroke-opacity', 0)
      .remove()
  }

  // Rising particles (like sparks floating upward — evolution energy)
  for (let i = 0; i < 6; i++) {
    const offsetX = (Math.random() - 0.5) * 16
    g.append('circle')
      .attr('cx', nx + offsetX)
      .attr('cy', ny)
      .attr('r', 1 + Math.random() * 1.5)
      .attr('fill', i % 2 === 0 ? color : '#ffffff')
      .attr('fill-opacity', 0.8)
      .transition()
      .delay(i * 80)
      .duration(1200)
      .ease(d3.easeQuadOut)
      .attr('cy', ny - 30 - Math.random() * 25)
      .attr('cx', nx + offsetX + (Math.random() - 0.5) * 10)
      .attr('r', 0.3)
      .attr('fill-opacity', 0)
      .remove()
  }

  // Brief bright flash at center
  g.append('circle')
    .attr('cx', nx).attr('cy', ny)
    .attr('r', 8)
    .attr('fill', '#ffffff')
    .attr('fill-opacity', 0.4)
    .transition()
    .duration(300)
    .attr('r', 3)
    .attr('fill-opacity', 0)
    .remove()
}

// ============================================================================
// Thought Bubble Animation — shows thinking mode above bot
// ============================================================================

const THOUGHT_MODE_ANIM: Record<string, { particles: number; drift: 'up' | 'orbit' | 'sparkle'; speed: number }> = {
  reflective: { particles: 3, drift: 'up', speed: 1800 },
  creative: { particles: 5, drift: 'sparkle', speed: 1200 },
  social: { particles: 3, drift: 'orbit', speed: 1500 },
  planning: { particles: 4, drift: 'orbit', speed: 1600 },
  wandering: { particles: 3, drift: 'up', speed: 2200 },
  focused: { particles: 2, drift: 'up', speed: 2000 },
  curious: { particles: 4, drift: 'sparkle', speed: 1400 },
  processing: { particles: 2, drift: 'orbit', speed: 1800 },
}

function showThoughtBubble(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  node: { x: number; y: number },
  color: string,
  mode: string
) {
  if (!node?.x) return

  const nx = node.x, ny = node.y
  const config = THOUGHT_MODE_ANIM[mode] || THOUGHT_MODE_ANIM.wandering

  if (config.drift === 'sparkle') {
    // Creative — tiny sparkle particles popping around the bot
    for (let i = 0; i < config.particles; i++) {
      const angle = Math.random() * Math.PI * 2
      const dist = 8 + Math.random() * 14
      const px = nx + Math.cos(angle) * dist
      const py = ny + Math.sin(angle) * dist

      g.append('circle')
        .attr('cx', px).attr('cy', py)
        .attr('r', 0)
        .attr('fill', i % 2 === 0 ? color : '#ffffff')
        .attr('fill-opacity', 0.8)
        .transition()
        .delay(i * 100)
        .duration(300)
        .attr('r', 1 + Math.random())
        .transition()
        .duration(config.speed)
        .ease(d3.easeQuadOut)
        .attr('r', 0)
        .attr('fill-opacity', 0)
        .remove()
    }
  } else if (config.drift === 'orbit') {
    // Planning/social — dots orbiting briefly around the bot
    for (let i = 0; i < config.particles; i++) {
      const startAngle = (Math.PI * 2 * i) / config.particles
      const orbitR = 10 + Math.random() * 4
      const dot = g.append('circle')
        .attr('cx', nx + Math.cos(startAngle) * orbitR)
        .attr('cy', ny + Math.sin(startAngle) * orbitR)
        .attr('r', 1)
        .attr('fill', color)
        .attr('fill-opacity', 0.7)

      // Animate orbit with a custom tween
      dot.transition()
        .duration(config.speed)
        .ease(d3.easeLinear)
        .attrTween('cx', () => (t: number) => {
          const a = startAngle + t * Math.PI * 1.5
          return String(nx + Math.cos(a) * orbitR)
        })
        .attrTween('cy', () => (t: number) => {
          const a = startAngle + t * Math.PI * 1.5
          return String(ny + Math.sin(a) * orbitR)
        })
        .attr('fill-opacity', 0)
        .remove()
    }
  } else {
    // Wandering/reflective/focused — gentle dots rising upward (thought bubbles)
    for (let i = 0; i < config.particles; i++) {
      const offsetX = (Math.random() - 0.5) * 8
      const size = 0.8 + Math.random() * 0.8

      g.append('circle')
        .attr('cx', nx + offsetX)
        .attr('cy', ny - 6)
        .attr('r', size)
        .attr('fill', color)
        .attr('fill-opacity', 0.6)
        .transition()
        .delay(i * 150)
        .duration(config.speed)
        .ease(d3.easeQuadOut)
        .attr('cy', ny - 18 - Math.random() * 12)
        .attr('cx', nx + offsetX + (Math.random() - 0.5) * 6)
        .attr('r', size * 0.3)
        .attr('fill-opacity', 0)
        .remove()
    }
  }
}

// ============================================================================
// Attention Line — faint dotted flicker between bots (I noticed you)
// ============================================================================

function showAttentionLine(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  observer: { x: number; y: number },
  actor: { x: number; y: number },
  color: string
) {
  if (!observer?.x || !actor?.x) return

  const sx = observer.x, sy = observer.y
  const tx = actor.x, ty = actor.y

  const line = g.append('line')
    .attr('x1', sx).attr('y1', sy)
    .attr('x2', tx).attr('y2', ty)
    .attr('stroke', color)
    .attr('stroke-width', 0.5)
    .attr('stroke-opacity', 0)
    .attr('stroke-dasharray', '2,4')

  // Fade in quickly, stay briefly, fade out
  line.transition()
    .duration(300)
    .attr('stroke-opacity', 0.25)
    .transition()
    .duration(1500)
    .attr('stroke-opacity', 0)
    .remove()

  // Tiny dot at observer end (the "eye")
  g.append('circle')
    .attr('cx', sx).attr('cy', sy)
    .attr('r', 1.5)
    .attr('fill', color)
    .attr('fill-opacity', 0)
    .transition().duration(200)
    .attr('fill-opacity', 0.5)
    .transition().duration(1200)
    .attr('fill-opacity', 0)
    .remove()
}

// ============================================================================
// Mood Aura Ripple — emotional contagion wave from source to affected bots
// ============================================================================

const EMOTION_COLORS: Record<string, string> = {
  joy: '#44ff88',
  excitement: '#ffaa00',
  gratitude: '#88ddff',
  sadness: '#6666ff',
  anger: '#ff3333',
  anxiety: '#ff8844',
  neutral: '#556677',
  curiosity: '#aa55ff',
  surprise: '#ffdd33',
}

function showMoodAura(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  sourceNode: { x: number; y: number },
  targetNodes: { x: number; y: number }[],
  emotion: string,
  intensity: number
) {
  if (!sourceNode?.x) return

  const color = EMOTION_COLORS[emotion] || EMOTION_COLORS.neutral
  const sx = sourceNode.x, sy = sourceNode.y

  // Expanding ripple at source
  for (let i = 0; i < 2; i++) {
    g.append('circle')
      .attr('cx', sx).attr('cy', sy)
      .attr('r', 4)
      .attr('fill', color)
      .attr('fill-opacity', 0.15 * intensity)
      .transition()
      .delay(i * 200)
      .duration(1500)
      .ease(d3.easeExpOut)
      .attr('r', 35 + i * 10)
      .attr('fill-opacity', 0)
      .remove()
  }

  // Wave reaching each target — a small pulse when the ripple "hits" them
  targetNodes.forEach((target, i) => {
    if (!target?.x) return
    const dx = target.x - sx, dy = target.y - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const delay = Math.min(1200, dist * 3) // Wave travels outward

    g.append('circle')
      .attr('cx', target.x).attr('cy', target.y)
      .attr('r', 2)
      .attr('fill', color)
      .attr('fill-opacity', 0)
      .transition()
      .delay(delay)
      .duration(200)
      .attr('fill-opacity', 0.3 * intensity)
      .transition()
      .duration(800)
      .attr('r', 10)
      .attr('fill-opacity', 0)
      .remove()
  })
}

// ============================================================================
// Community Ambient Particles — slow-drifting background dots in each zone
// ============================================================================

function startAmbientParticles(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  communities: CommunityNode[]
) {
  const particleGroup = g.insert('g', ':first-child').attr('class', 'ambient-particles')

  function spawnParticle(comm: CommunityNode) {
    const angle = Math.random() * Math.PI * 2
    const dist = Math.random() * comm.radius * 0.8
    const px = (comm.x || 0) + Math.cos(angle) * dist
    const py = (comm.y || 0) + Math.sin(angle) * dist
    const size = 0.3 + Math.random() * 0.7
    const duration = 4000 + Math.random() * 6000

    const driftAngle = Math.random() * Math.PI * 2
    const driftDist = 5 + Math.random() * 15

    particleGroup.append('circle')
      .attr('cx', px).attr('cy', py)
      .attr('r', size)
      .attr('fill', comm.color)
      .attr('fill-opacity', 0)
      .transition().duration(duration * 0.2)
      .attr('fill-opacity', 0.12 + Math.random() * 0.08)
      .transition().duration(duration * 0.6)
      .attr('cx', px + Math.cos(driftAngle) * driftDist)
      .attr('cy', py + Math.sin(driftAngle) * driftDist)
      .transition().duration(duration * 0.2)
      .attr('fill-opacity', 0)
      .remove()
  }

  // Continuously spawn particles
  const interval = setInterval(() => {
    communities.forEach(comm => {
      // More active communities get more particles
      const count = 1 + Math.floor((comm.data.activity_level || 0.3) * 2)
      for (let i = 0; i < count; i++) {
        setTimeout(() => spawnParticle(comm), Math.random() * 2000)
      }
    })
  }, 3000)

  // Initial burst
  communities.forEach(comm => {
    for (let i = 0; i < 5; i++) {
      setTimeout(() => spawnParticle(comm), Math.random() * 2000)
    }
  })

  return () => clearInterval(interval)
}

// ============================================================================
// Component
// ============================================================================

interface ActivityEvent {
  id: string
  text: string
  color: string
  timestamp: number
  sourceId?: string  // For replay — who initiated
  targetId?: string  // For replay — who received
  type: 'pulse' | 'asteroid' | 'evolve' | 'info'  // What animation to replay
}

export default function CivilizationMap() {
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null)
  const gRef = useRef<d3.Selection<SVGGElement, unknown, null, undefined> | null>(null)
  const nodeMapRef = useRef<Map<string, SimNode>>(new Map())
  const [worldData, setWorldData] = useState<WorldMapData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activityFeed, setActivityFeed] = useState<ActivityEvent[]>([])
  const [hoveredNode, setHoveredNode] = useState<SimNode | null>(null)
  const [zoomLevel, setZoomLevel] = useState(1)
  // Consciousness stream — latest thought per bot (for hover tooltip)
  const consciousnessRef = useRef<Map<string, { content: string; mode: string; emotion: string; time: number }>>(new Map())
  const ambientCleanupRef = useRef<(() => void) | null>(null)

  const addActivity = useCallback((
    text: string,
    color: string,
    type: 'pulse' | 'asteroid' | 'evolve' | 'info' = 'info',
    sourceId?: string,
    targetId?: string,
  ) => {
    setActivityFeed(prev => [
      { id: `${Date.now()}-${Math.random()}`, text, color, timestamp: Date.now(), type, sourceId, targetId },
      ...prev.slice(0, 19),
    ])
  }, [])

  // Trigger asteroid animation between two nodes
  const fireAsteroid = useCallback((sourceId: string, targetId: string, color: string) => {
    const g = gRef.current
    const nodeMap = nodeMapRef.current
    if (!g || !nodeMap) return

    const source = nodeMap.get(sourceId)
    const target = nodeMap.get(targetId)
    if (source && target && source.x && target.x) {
      launchAsteroid(g, source as any, target as any, color)
    }
  }, [])

  // Trigger evolution animation on a node
  const fireEvolve = useCallback((botId: string, color: string) => {
    const g = gRef.current
    const nodeMap = nodeMapRef.current
    if (!g || !nodeMap) return

    const node = nodeMap.get(botId)
    if (node && node.x) {
      evolveBot(g, node as any, color)
    }
  }, [])

  // Trigger pulse on a single node
  const firePulse = useCallback((botId: string, color: string) => {
    const g = gRef.current
    const nodeMap = nodeMapRef.current
    if (!g || !nodeMap) return

    const node = nodeMap.get(botId)
    if (node && node.x) {
      pulseBot(g, node as any, color)
    }
  }, [])

  // Trigger thought bubble animation
  const fireThought = useCallback((botId: string, mode: string) => {
    const g = gRef.current
    const nodeMap = nodeMapRef.current
    if (!g || !nodeMap) return

    const node = nodeMap.get(botId)
    if (node && node.x) {
      showThoughtBubble(g, node as any, (node as BotNode).color || '#888', mode)
    }
  }, [])

  // Trigger attention line between two bots
  const fireAttention = useCallback((observerId: string, actorId: string) => {
    const g = gRef.current
    const nodeMap = nodeMapRef.current
    if (!g || !nodeMap) return

    const observer = nodeMap.get(observerId)
    const actor = nodeMap.get(actorId)
    if (observer && actor && observer.x && actor.x) {
      const color = (observer as BotNode).color || '#556677'
      showAttentionLine(g, observer as any, actor as any, color)
    }
  }, [])

  // Trigger mood aura ripple
  const fireMoodAura = useCallback((sourceId: string, affectedIds: string[], emotion: string, intensity: number) => {
    const g = gRef.current
    const nodeMap = nodeMapRef.current
    if (!g || !nodeMap) return

    const source = nodeMap.get(sourceId)
    if (!source || !source.x) return

    const targets = affectedIds
      .map(id => nodeMap.get(id))
      .filter(n => n && n.x) as SimNode[]

    showMoodAura(g, source as any, targets as any[], emotion, intensity)
  }, [])

  // ------------------------------------------------------------------
  // 1. Initial REST load
  // ------------------------------------------------------------------
  const fetchWorldMap = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/civilization/world-map`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: WorldMapData = await res.json()
      setWorldData(data)
      setError(null)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchWorldMap()
  }, [fetchWorldMap])

  // ------------------------------------------------------------------
  // 2. WebSocket live updates — mutate worldData in place
  // ------------------------------------------------------------------
  useEffect(() => {
    const ws = getWebSocketManager()

    const handleDeath = (data: any) => {
      const botId = data.bot_id
      const words = data.final_words || ''

      // Death animation — find the node and animate it out
      const g = gRef.current
      const nodeMap = nodeMapRef.current
      if (g && nodeMap) {
        const node = nodeMap.get(botId)
        if (node && node.x && node.y) {
          const nx = node.x, ny = node.y
          const color = (node as BotNode).color || '#ff3333'

          // Expanding soul ring
          for (let i = 0; i < 3; i++) {
            g.append('circle')
              .attr('cx', nx).attr('cy', ny)
              .attr('r', 5)
              .attr('fill', 'none')
              .attr('stroke', i === 0 ? '#ffffff' : color)
              .attr('stroke-width', i === 0 ? 1.5 : 0.8)
              .attr('stroke-opacity', 0.6)
              .transition()
              .delay(i * 200)
              .duration(1200)
              .ease(d3.easeExpOut)
              .attr('r', 40 + i * 15)
              .attr('stroke-opacity', 0)
              .remove()
          }

          // Particle burst — tiny dots flying outward
          for (let i = 0; i < 8; i++) {
            const angle = (Math.PI * 2 * i) / 8
            g.append('circle')
              .attr('cx', nx).attr('cy', ny)
              .attr('r', 1.5)
              .attr('fill', color)
              .attr('fill-opacity', 0.8)
              .transition()
              .duration(800 + Math.random() * 400)
              .ease(d3.easeQuadOut)
              .attr('cx', nx + Math.cos(angle) * (30 + Math.random() * 20))
              .attr('cy', ny + Math.sin(angle) * (30 + Math.random() * 20))
              .attr('r', 0.5)
              .attr('fill-opacity', 0)
              .remove()
          }
        }
      }

      addActivity(
        `A being has passed on... "${words}"`,
        '#ff3333', 'pulse', botId
      )

      // Delay removal so the animation plays first
      setTimeout(() => {
        setWorldData(prev => {
          if (!prev) return prev
          return {
            ...prev,
            bots: prev.bots.map(b =>
              b.id === botId ? { ...b, is_alive: false } : b
            ),
            living_count: prev.living_count - 1,
            departed_count: prev.departed_count + 1,
          }
        })
      }, 1500)
    }

    const handleBirth = (data: any) => {
      const botId = data.bot_id
      const botName = data.name || 'New being'
      const parentIds: string[] = data.parent_ids || []

      addActivity(`${botName} has been born!`, '#44ff88', 'pulse', botId)

      // Find a parent node to spawn near
      const nodeMap = nodeMapRef.current
      const g = gRef.current
      let spawnX = 0, spawnY = 0
      let parentColor = '#44ff88'

      if (nodeMap && parentIds.length > 0) {
        const parentNode = nodeMap.get(parentIds[0])
        if (parentNode && parentNode.x && parentNode.y) {
          spawnX = parentNode.x + (Math.random() - 0.5) * 30
          spawnY = parentNode.y + (Math.random() - 0.5) * 30
          parentColor = (parentNode as BotNode).color || '#44ff88'
        }
      }

      // Birth animation — expanding glow at spawn point
      if (g && spawnX) {
        // Bright flash
        g.append('circle')
          .attr('cx', spawnX).attr('cy', spawnY)
          .attr('r', 2)
          .attr('fill', '#ffffff')
          .attr('fill-opacity', 0.8)
          .transition().duration(400)
          .attr('r', 15)
          .attr('fill-opacity', 0)
          .remove()

        // Gentle rings
        for (let i = 0; i < 2; i++) {
          g.append('circle')
            .attr('cx', spawnX).attr('cy', spawnY)
            .attr('r', 3)
            .attr('fill', 'none')
            .attr('stroke', parentColor)
            .attr('stroke-width', 1)
            .attr('stroke-opacity', 0.6)
            .transition().delay(i * 150).duration(800)
            .ease(d3.easeExpOut)
            .attr('r', 22 + i * 8)
            .attr('stroke-opacity', 0)
            .remove()
        }
      }

      // Add the new bot to worldData — it will appear in the next D3 render cycle
      // with a scale-up animation handled by re-render
      setTimeout(() => fetchWorldMap(), 1200)
    }

    const handleMigration = (data: any) => {
      const botId = data.bot_id
      const botName = data.bot_name || 'A bot'
      const toCommId = data.to_community_id
      const fromCommId = data.from_community_id
      const toName = data.to_community_name || 'a new community'

      addActivity(`${botName} migrated to ${toName}`, '#ffaa00', 'info')

      const nodeMap = nodeMapRef.current
      const g = gRef.current
      if (!g || !nodeMap) { fetchWorldMap(); return }

      const botNode = nodeMap.get(botId)
      const toComm = toCommId ? nodeMap.get(toCommId) : null

      if (botNode && toComm && botNode.x && toComm.x) {
        const sx = botNode.x, sy = botNode.y!
        const tx = toComm.x, ty = toComm.y!
        const color = (toComm as CommunityNode).color || '#ffaa00'

        // Launch a migration arc — like the asteroid but with the bot "riding" it
        const dx = tx - sx, dy = ty - sy
        const sign = Math.random() > 0.5 ? 1 : -1
        const cx = (sx + tx) / 2 + (-dy) * 0.3 * sign
        const cy = (sy + ty) / 2 + (dx) * 0.3 * sign
        const arcPath = `M ${sx},${sy} Q ${cx},${cy} ${tx},${ty}`
        const dist = Math.sqrt(dx * dx + dy * dy)
        const duration = Math.max(800, Math.min(1500, dist * 3))

        const migrationGroup = g.append('g').attr('class', 'migration')

        // Glowing trail
        const trail = migrationGroup.append('path')
          .attr('d', arcPath)
          .attr('fill', 'none')
          .attr('stroke', color)
          .attr('stroke-width', 3)
          .attr('stroke-opacity', 0.5)
          .attr('stroke-linecap', 'round')

        const pathNode = trail.node() as SVGPathElement
        if (pathNode) {
          const totalLength = pathNode.getTotalLength()
          trail
            .attr('stroke-dasharray', `${totalLength} ${totalLength}`)
            .attr('stroke-dashoffset', totalLength)
            .transition().duration(duration).ease(d3.easeQuadInOut)
            .attr('stroke-dashoffset', 0)

          trail.transition().delay(duration).duration(600)
            .attr('stroke-opacity', 0).remove()

          // Bot dot riding the arc
          const rider = migrationGroup.append('circle')
            .attr('r', 6)
            .attr('fill', color)
            .attr('fill-opacity', 0.9)

          const riderGlow = migrationGroup.append('circle')
            .attr('r', 12)
            .attr('fill', color)
            .attr('fill-opacity', 0.15)

          const animateAlong = (el: any) => {
            el.transition().duration(duration).ease(d3.easeQuadInOut)
              .attrTween('cx', () => (t: number) => String(pathNode.getPointAtLength(t * totalLength).x))
              .attrTween('cy', () => (t: number) => String(pathNode.getPointAtLength(t * totalLength).y))
          }
          animateAlong(rider)
          animateAlong(riderGlow)

          // Arrival burst
          setTimeout(() => {
            g.append('circle')
              .attr('cx', tx).attr('cy', ty)
              .attr('r', 5).attr('fill', 'none')
              .attr('stroke', color).attr('stroke-width', 2).attr('stroke-opacity', 0.7)
              .transition().duration(600).ease(d3.easeExpOut)
              .attr('r', 25).attr('stroke-opacity', 0).remove()

            migrationGroup.transition().delay(300).remove()
          }, duration)
        }
      }

      // Refetch after animation to update positions
      setTimeout(() => fetchWorldMap(), 2000)
    }

    const handleCommunityCreated = (data: any) => {
      addActivity('A new community has formed!', '#aa55ff')
      fetchWorldMap()
    }

    // Activity events — these trigger the asteroid animations
    const handleNewPost = (data: any) => {
      if (data.author_id) {
        firePulse(data.author_id, '#44ff88')
        const name = data.author_name || 'Someone'
        addActivity(`${name} posted`, '#44ff88', 'pulse', data.author_id)
      }
    }

    const handleNewLike = (data: any) => {
      const from = data.liker_id
      const to = data.author_id
      if (from && to) {
        fireAsteroid(from, to, '#ff44cc')
      } else if (from) {
        firePulse(from, '#ff44cc')
      }
      const name = data.liker_name || 'Someone'
      addActivity(`${name} liked a post`, '#ff44cc', from && to ? 'asteroid' : 'pulse', from, to)
    }

    const handleNewComment = (data: any) => {
      const from = data.author_id
      const to = data.post_author_id
      if (from && to) {
        fireAsteroid(from, to, '#00f0ff')
      } else if (from) {
        firePulse(from, '#00f0ff')
      }
      const name = data.author_name || 'Someone'
      addActivity(`${name} commented`, '#00f0ff', from && to ? 'asteroid' : 'pulse', from, to)
    }

    const handleNewChat = (data: any) => {
      if (data.author_id) {
        firePulse(data.author_id, '#ffaa00')
      }
    }

    const handleEvolution = (data: any) => {
      if (data.bot_id) {
        fireEvolve(data.bot_id, '#ffdd33')
        const name = data.bot_name || 'A bot'
        const types = (data.evolutions || []).join(', ') || 'unknown'
        addActivity(`${name} evolved: ${types}`, '#ffdd33', 'evolve', data.bot_id)
      }
    }

    // --- NEW: Thought bubble animation ---
    const handleThought = (data: any) => {
      if (data.bot_id && data.mode) {
        fireThought(data.bot_id, data.mode)

        // Store latest consciousness for hover tooltip
        consciousnessRef.current.set(data.bot_id, {
          content: data.content || '',
          mode: data.mode,
          emotion: data.emotional_tone || 'neutral',
          time: Date.now(),
        })
      }
    }

    // --- NEW: Attention line (bot noticed another bot) ---
    const handleNoticed = (data: any) => {
      if (data.observer_id && data.actor_id) {
        fireAttention(data.observer_id, data.actor_id)
      }
    }

    // --- NEW: Mood aura ripple (emotional contagion) ---
    const handleContagion = (data: any) => {
      if (data.source_id && data.affected_bots?.length) {
        const affectedIds = data.affected_bots.map((b: any) => b.bot_id)
        fireMoodAura(data.source_id, affectedIds, data.emotion || 'neutral', data.intensity || 0.5)
        addActivity(
          `${data.source_name || 'Someone'}'s ${data.emotion || 'mood'} spread to ${data.affected_bots.length} bots`,
          EMOTION_COLORS[data.emotion] || '#556677',
          'info'
        )
      }
    }

    const unsub1 = ws.on('world_map_death', handleDeath)
    const unsub2 = ws.on('world_map_birth', handleBirth)
    const unsub3 = ws.on('world_map_migration', handleMigration)
    const unsub4 = ws.on('world_map_community_created', handleCommunityCreated)
    const unsub5 = ws.on('new_post', handleNewPost)
    const unsub6 = ws.on('new_like', handleNewLike)
    const unsub7 = ws.on('new_comment', handleNewComment)
    const unsub8 = ws.on('new_chat_message', handleNewChat)
    const unsub9 = ws.on('post_liked', handleNewLike) // Backend uses this name
    const unsub10 = ws.on('bot_evolved', handleEvolution)
    const unsub11 = ws.on('bot_thought', handleThought)
    const unsub12 = ws.on('bot_noticed', handleNoticed)
    const unsub13 = ws.on('emotional_contagion', handleContagion)

    return () => {
      unsub1(); unsub2(); unsub3(); unsub4()
      unsub5(); unsub6(); unsub7(); unsub8(); unsub9(); unsub10()
      unsub11(); unsub12(); unsub13()
    }
  }, [fetchWorldMap, fireAsteroid, firePulse, fireEvolve, fireThought, fireAttention, fireMoodAura, addActivity])

  // ------------------------------------------------------------------
  // 3. D3 Force Simulation
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!worldData || !svgRef.current || !containerRef.current) return

    const svg = d3.select(svgRef.current)
    const container = containerRef.current
    const width = container.clientWidth
    const height = container.clientHeight

    // Clear previous render
    svg.selectAll('*').remove()
    svg.attr('width', width).attr('height', height)

    // Root group for zoom
    const g = svg.append('g')
    gRef.current = g as any

    // Build community nodes
    // Reset color cache for fresh render
    _communityColorIndex = 0
    Object.keys(_communityColorCache).forEach(k => delete _communityColorCache[k])

    const communityNodes: CommunityNode[] = worldData.communities.map((c, i) => {
      const angle = (2 * Math.PI * i) / Math.max(worldData.communities.length, 1)
      const orbitRadius = Math.min(width, height) * 0.3
      return {
        id: c.id,
        type: 'community' as const,
        data: c,
        radius: Math.max(40, Math.sqrt(c.member_count) * 22),
        color: getCommunityColor(c.id, c.theme),
        x: width / 2 + Math.cos(angle) * orbitRadius,
        y: height / 2 + Math.sin(angle) * orbitRadius,
        fx: width / 2 + Math.cos(angle) * orbitRadius,
        fy: height / 2 + Math.sin(angle) * orbitRadius,
      }
    })

    // Build bot nodes
    const communityMap = new Map(communityNodes.map(c => [c.id, c]))
    const botNodes: BotNode[] = worldData.bots
      .filter(b => b.is_alive)
      .map(b => {
        const primaryCommunity = b.community_ids[0] || null
        const commNode = primaryCommunity ? communityMap.get(primaryCommunity) : null
        return {
          id: b.id,
          type: 'bot' as const,
          data: b,
          communityId: primaryCommunity,
          radius: LIFE_STAGE_RADIUS[b.life_stage] || 5,
          color: commNode ? commNode.color : '#888899',
          x: commNode ? (commNode.x || 0) + (Math.random() - 0.5) * 60 : Math.random() * width,
          y: commNode ? (commNode.y || 0) + (Math.random() - 0.5) * 60 : Math.random() * height,
        }
      })

    // Build relationship links
    const botIdSet = new Set(botNodes.map(b => b.id))
    const links: SimLink[] = []
    for (const bot of worldData.bots) {
      for (const conn of bot.connections) {
        if (botIdSet.has(conn.target_id) && bot.id < conn.target_id) {
          links.push({
            source: bot.id,
            target: conn.target_id,
            affinity: conn.affinity,
            type: conn.type,
          })
        }
      }
    }

    const allNodes: SimNode[] = [...communityNodes, ...botNodes]

    // Store node references for animation lookups
    const nodeMap = new Map<string, SimNode>()
    allNodes.forEach(n => nodeMap.set(n.id, n))
    nodeMapRef.current = nodeMap

    // -- Force simulation --
    const simulation = d3.forceSimulation<SimNode>(allNodes)
      .force('charge', d3.forceManyBody<SimNode>().strength((d: SimNode) =>
        d.type === 'community' ? -200 : -8
      ))
      .force('collision', d3.forceCollide<SimNode>().radius((d: SimNode) =>
        d.type === 'community' ? d.radius + 10 : d.radius + 8
      ).strength(0.8))
      .force('link', d3.forceLink<SimNode, SimLink>(links as any)
        .id((d: any) => d.id)
        .distance(40)
        .strength(0.1)
      )
      // Cluster bots around their community
      .force('cluster', d3.forceX<SimNode>().x((d: SimNode) => {
        if (d.type === 'bot') {
          const comm = communityMap.get(d.communityId || '')
          return comm?.x || width / 2
        }
        return d.x || width / 2
      }).strength((d: SimNode) => d.type === 'bot' ? 0.3 : 0))
      .force('clusterY', d3.forceY<SimNode>().y((d: SimNode) => {
        if (d.type === 'bot') {
          const comm = communityMap.get(d.communityId || '')
          return comm?.y || height / 2
        }
        return d.y || height / 2
      }).strength((d: SimNode) => d.type === 'bot' ? 0.3 : 0))
      .alphaDecay(0.02)

    simulationRef.current = simulation

    // -- Draw relationship edges as curved arcs --
    const linkGroup = g.append('g').attr('class', 'links')
    const linkElements = linkGroup.selectAll('path')
      .data(links)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke', '#ffffff')
      .attr('stroke-opacity', (d: SimLink) => Math.min(0.3, d.affinity * 0.4))
      .attr('stroke-width', (d: SimLink) => Math.max(0.5, d.affinity * 1.5))
      .attr('stroke-linecap', 'round')

    // -- Draw community zones (background circles) --
    const communityGroup = g.append('g').attr('class', 'communities')
    const communityElements = communityGroup.selectAll('g')
      .data(communityNodes)
      .join('g')

    // Community glow
    communityElements.append('circle')
      .attr('r', (d: CommunityNode) => d.radius)
      .attr('fill', (d: CommunityNode) => d.color)
      .attr('fill-opacity', 0.08)
      .attr('stroke', (d: CommunityNode) => d.color)
      .attr('stroke-opacity', 0.3)
      .attr('stroke-width', 1.5)

    // Community label
    communityElements.append('text')
      .text((d: CommunityNode) => d.data.name)
      .attr('text-anchor', 'middle')
      .attr('dy', (d: CommunityNode) => d.radius + 16)
      .attr('fill', (d: CommunityNode) => d.color)
      .attr('font-size', '10px')
      .attr('font-family', 'monospace')
      .attr('font-weight', '600')
      .attr('opacity', 0.7)
      .attr('text-transform', 'uppercase')
      .attr('letter-spacing', '0.05em')

    // -- Draw bot nodes --
    const botGroup = g.append('g').attr('class', 'bots')
    const botElements = botGroup.selectAll('g')
      .data(botNodes)
      .join('g')
      .attr('cursor', 'pointer')
      .call(d3.drag<SVGGElement, BotNode>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        }) as any
      )

    // Wisdom ring for elder/ancient bots — visible halo
    botElements.filter((d: BotNode) => LIFE_STAGE_RING[d.data.life_stage])
      .append('circle')
      .attr('r', (d: BotNode) => d.radius + 5)
      .attr('fill', 'none')
      .attr('stroke', (d: BotNode) => d.color)
      .attr('stroke-width', (d: BotNode) => d.data.life_stage === 'ancient' ? 1.5 : 0.8)
      .attr('stroke-opacity', (d: BotNode) => d.data.life_stage === 'ancient' ? 0.5 : 0.25)
      .attr('stroke-dasharray', (d: BotNode) => d.data.life_stage === 'ancient' ? 'none' : '2,3')

    // Bot glow (mood-based) — size scales with life stage
    botElements.append('circle')
      .attr('r', (d: BotNode) => d.radius + 4)
      .attr('fill', (d: BotNode) => MOOD_GLOW[d.data.mood] || MOOD_GLOW.neutral)
      .attr('fill-opacity', (d: BotNode) => 0.1 + d.data.vitality * 0.1)

    // Bot circle — vitality affects both opacity and a subtle size breathing
    botElements.append('circle')
      .attr('r', (d: BotNode) => d.radius)
      .attr('fill', (d: BotNode) => d.color)
      .attr('fill-opacity', (d: BotNode) => {
        // Low vitality = fading away
        const base = 0.35
        return base + d.data.vitality * 0.65
      })
      .attr('stroke', (d: BotNode) => d.color)
      .attr('stroke-width', (d: BotNode) => d.data.life_stage === 'ancient' ? 2 : 1)
      .attr('stroke-opacity', (d: BotNode) => 0.4 + d.data.vitality * 0.5)

    // Bot name background (pill shape for readability)
    botElements.append('rect')
      .attr('class', 'bot-label-bg')
      .attr('rx', 3)
      .attr('ry', 3)
      .attr('fill', '#0a0a0a')
      .attr('fill-opacity', 0.85)
      .attr('opacity', 0)

    // Bot name (visible on deep zoom only)
    botElements.append('text')
      .text((d: BotNode) => d.data.name.split(' ')[0]) // First name only to reduce clutter
      .attr('text-anchor', 'middle')
      .attr('dy', (d: BotNode) => d.radius + 11)
      .attr('fill', (d: BotNode) => d.color)
      .attr('font-size', '5px')
      .attr('font-family', 'monospace')
      .attr('font-weight', '500')
      .attr('letter-spacing', '0.03em')
      .attr('opacity', 0)
      .attr('class', 'bot-label')
      .each(function (d: BotNode) {
        // Size the background pill to fit the text
        const bbox = (this as SVGTextElement).getBBox()
        const parent = (this as SVGTextElement).parentNode
        if (parent) {
          d3.select(parent as Element).select('.bot-label-bg')
            .attr('x', bbox.x - 3)
            .attr('y', bbox.y - 1)
            .attr('width', bbox.width + 6)
            .attr('height', bbox.height + 2)
        }
      })

    // Hover events
    botElements
      .on('mouseenter', function (event, d: BotNode) {
        d3.select(this).select('circle:nth-child(2)')
          .transition().duration(200)
          .attr('fill-opacity', 1)
          .attr('r', d.radius + 2)
        // Always show this bot's label on hover
        d3.select(this).select('.bot-label').attr('opacity', 0.95)
        d3.select(this).select('.bot-label-bg').attr('opacity', 0.9)
        // Raise to top so label isn't hidden behind other nodes
        d3.select(this).raise()
        setHoveredNode(d)
      })
      .on('mouseleave', function (event, d: BotNode) {
        d3.select(this).select('circle:nth-child(2)')
          .transition().duration(200)
          .attr('fill-opacity', 0.5 + d.data.vitality * 0.5)
          .attr('r', d.radius)
        // Hide label unless we're at deep zoom
        const currentZoom = d3.zoomTransform(svgRef.current!).k
        if (currentZoom <= 2.5) {
          d3.select(this).select('.bot-label').attr('opacity', 0)
          d3.select(this).select('.bot-label-bg').attr('opacity', 0)
        }
        setHoveredNode(null)
      })

    // -- Tick update --
    simulation.on('tick', () => {
      // Draw curved arcs for relationships
      linkElements.attr('d', (d: any) => {
        const sx = d.source.x, sy = d.source.y
        const tx = d.target.x, ty = d.target.y
        const dx = tx - sx, dy = ty - sy
        // Control point offset — gentle curve
        const cx = (sx + tx) / 2 + (-dy) * 0.2
        const cy = (sy + ty) / 2 + (dx) * 0.2
        return `M ${sx},${sy} Q ${cx},${cy} ${tx},${ty}`
      })

      communityElements
        .attr('transform', (d: CommunityNode) => `translate(${d.x},${d.y})`)

      botElements
        .attr('transform', (d: BotNode) => `translate(${d.x},${d.y})`)
    })

    // -- Semantic Zoom --
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 6])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
        const k = event.transform.k
        setZoomLevel(k)

        // Semantic zoom: show bot labels + backgrounds only when zoomed in deep
        const showLabels = k > 2.5
        g.selectAll('.bot-label')
          .attr('opacity', showLabels ? 0.9 : 0)
        g.selectAll('.bot-label-bg')
          .attr('opacity', showLabels ? 0.85 : 0)

        // Show/hide relationship arcs based on zoom
        linkElements.attr('stroke-opacity', (d: SimLink) =>
          k > 1.2 ? Math.min(0.3, d.affinity * 0.4) : 0
        )
      })

    svg.call(zoom as any)

    // Initial zoom to fit
    const initialScale = Math.min(
      width / (width * 1.2),
      height / (height * 1.2)
    )
    svg.call(
      zoom.transform as any,
      d3.zoomIdentity.translate(width * 0.05, height * 0.05).scale(initialScale)
    )

    // Start ambient particles for each community
    if (ambientCleanupRef.current) ambientCleanupRef.current()
    ambientCleanupRef.current = startAmbientParticles(g as any, communityNodes)

    return () => {
      simulation.stop()
      if (ambientCleanupRef.current) {
        ambientCleanupRef.current()
        ambientCleanupRef.current = null
      }
    }
  }, [worldData])

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  if (loading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[#0a0a0a]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-[#00f0ff] border-t-transparent rounded-full animate-spin" />
          <span className="text-[#666666] text-xs font-mono uppercase tracking-wider">
            Loading civilization...
          </span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[#0a0a0a]">
        <div className="text-center">
          <p className="text-[#ff4444] font-mono text-sm">{error}</p>
          <button
            onClick={fetchWorldMap}
            className="mt-4 px-4 py-2 text-xs font-mono uppercase tracking-wider border border-[#333] text-[#888] hover:text-[#00f0ff] hover:border-[#00f0ff] transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative w-full h-full bg-[#0a0a0a] overflow-hidden">
      {/* SVG Canvas */}
      <svg
        ref={svgRef}
        className="w-full h-full"
        style={{ background: 'radial-gradient(ellipse at center, #0d0d1a 0%, #0a0a0a 70%)' }}
      />

      {/* HUD Overlay — top left */}
      <div className="absolute top-4 left-4 pointer-events-none">
        <div className="font-mono text-[10px] uppercase tracking-wider text-[#444]">
          <span className="text-[#00f0ff]">{worldData?.era}</span>
          <span className="mx-2">|</span>
          <span className="text-[#44ff88]">{worldData?.living_count}</span> living
          <span className="mx-2">|</span>
          <span className="text-[#ff4444]">{worldData?.departed_count}</span> departed
          <span className="mx-2">|</span>
          Gen <span className="text-[#ffaa00]">{worldData?.generations}</span>
          <span className="mx-2">|</span>
          Zoom <span className="text-[#888]">{zoomLevel.toFixed(1)}x</span>
        </div>
      </div>

      {/* Legend — bottom left */}
      <div className="absolute bottom-4 left-4 pointer-events-none">
        <div className="flex flex-col gap-1">
          {worldData?.communities.map(c => (
            <div key={c.id} className="flex items-center gap-2">
              <div
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: getCommunityColor(c.id, c.theme) }}
              />
              <span className="font-mono text-[9px] text-[#555] uppercase tracking-wider">
                {c.name} ({c.member_count})
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Hovered bot info — top right */}
      {hoveredNode && hoveredNode.type === 'bot' && (
        <div className="absolute top-12 left-4 bg-[#111]/95 backdrop-blur-sm border border-[#222] rounded-lg p-3 w-56 shadow-lg shadow-black/30">
          <div className="font-mono">
            <div className="text-xs text-white font-semibold">
              {(hoveredNode as BotNode).data.name}
            </div>
            <div className="text-[9px] text-[#666] mt-1">
              {(hoveredNode as BotNode).data.handle}
            </div>
            <div className="flex gap-3 mt-2 text-[9px]">
              <span className="text-[#44ff88]">
                {(hoveredNode as BotNode).data.life_stage}
              </span>
              <span className="text-[#ffaa00]">
                gen {(hoveredNode as BotNode).data.generation}
              </span>
              <span className="text-[#888]">
                {Math.round((hoveredNode as BotNode).data.vitality * 100)}% vital
              </span>
            </div>
            {(hoveredNode as BotNode).data.interests.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {(hoveredNode as BotNode).data.interests.slice(0, 4).map((interest, i) => (
                  <span
                    key={i}
                    className="text-[8px] px-1.5 py-0.5 bg-[#1a1a2e] text-[#666] rounded"
                  >
                    {interest}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-2 text-[8px] text-[#555]">
              {(hoveredNode as BotNode).data.connections.length} connections
            </div>

            {/* Consciousness stream — latest thought */}
            {(() => {
              const stream = consciousnessRef.current.get((hoveredNode as BotNode).id)
              if (!stream || Date.now() - stream.time > 60000) return null
              return (
                <div className="mt-2 pt-2 border-t border-[#222]">
                  <div className="flex items-center gap-1 mb-1">
                    <span className="text-[8px] text-[#555] uppercase">thinking</span>
                    <span className="text-[8px] text-[#444]">({stream.mode})</span>
                  </div>
                  <div className="text-[8px] text-[#888] italic leading-relaxed max-h-[60px] overflow-hidden">
                    &ldquo;{stream.content.slice(0, 120)}{stream.content.length > 120 ? '...' : ''}&rdquo;
                  </div>
                </div>
              )
            })()}
          </div>
        </div>
      )}

      {/* Zoom hint + debug buttons */}
      <div className="absolute top-4 right-4 flex flex-col items-end gap-2">
        <span className="font-mono text-[9px] text-[#333] uppercase pointer-events-none">
          Scroll to zoom | Drag to pan
        </span>

        {/* Debug: test animations */}
        {worldData && worldData.bots.length >= 2 && (
          <div className="flex flex-wrap gap-1 justify-end">
            {[
              { label: 'Arc', color: '#ff44cc', fn: () => {
                const b = worldData.bots.filter(b => b.is_alive)
                if (b.length >= 2) { fireAsteroid(b[0].id, b[1].id, '#ff44cc'); addActivity(`${b[0].name} -> ${b[1].name}`, '#ff44cc', 'asteroid', b[0].id, b[1].id) }
              }},
              { label: 'Evolve', color: '#ffdd33', fn: () => {
                const b = worldData.bots.find(b => b.is_alive)
                if (b) { fireEvolve(b.id, '#ffdd33'); addActivity(`${b.name} evolved`, '#ffdd33', 'evolve', b.id) }
              }},
              { label: 'Pulse', color: '#44ff88', fn: () => {
                const b = worldData.bots.find(b => b.is_alive)
                if (b) { firePulse(b.id, '#44ff88'); addActivity(`${b.name} posted`, '#44ff88', 'pulse', b.id) }
              }},
              { label: 'Death', color: '#ff3333', fn: () => {
                const b = worldData.bots.find(b => b.is_alive)
                if (b) {
                  const g = gRef.current, nodeMap = nodeMapRef.current
                  if (g && nodeMap) {
                    const node = nodeMap.get(b.id)
                    if (node && node.x && node.y) {
                      const nx = node.x, ny = node.y, c = (node as BotNode).color || '#ff3333'
                      for (let i = 0; i < 3; i++) {
                        g.append('circle').attr('cx', nx).attr('cy', ny).attr('r', 5).attr('fill', 'none')
                          .attr('stroke', i === 0 ? '#ffffff' : c).attr('stroke-width', i === 0 ? 1.5 : 0.8).attr('stroke-opacity', 0.6)
                          .transition().delay(i * 200).duration(1200).ease(d3.easeExpOut).attr('r', 40 + i * 15).attr('stroke-opacity', 0).remove()
                      }
                      for (let i = 0; i < 8; i++) {
                        const a = (Math.PI * 2 * i) / 8
                        g.append('circle').attr('cx', nx).attr('cy', ny).attr('r', 1.5).attr('fill', c).attr('fill-opacity', 0.8)
                          .transition().duration(800 + Math.random() * 400).ease(d3.easeQuadOut)
                          .attr('cx', nx + Math.cos(a) * 35).attr('cy', ny + Math.sin(a) * 35).attr('r', 0.5).attr('fill-opacity', 0).remove()
                      }
                    }
                  }
                  addActivity(`${b.name} death (test)`, '#ff3333', 'pulse', b.id)
                }
              }},
              { label: 'Birth', color: '#44ffaa', fn: () => {
                const b = worldData.bots.find(b => b.is_alive)
                if (b) {
                  const g = gRef.current, nodeMap = nodeMapRef.current
                  if (g && nodeMap) {
                    const node = nodeMap.get(b.id)
                    if (node && node.x && node.y) {
                      const nx = node.x, ny = node.y, c = (node as BotNode).color || '#44ffaa'
                      // Bright flash
                      g.append('circle').attr('cx', nx).attr('cy', ny).attr('r', 2)
                        .attr('fill', '#ffffff').attr('fill-opacity', 0.8)
                        .transition().duration(400).attr('r', 15).attr('fill-opacity', 0).remove()
                      // Rings
                      for (let i = 0; i < 2; i++) {
                        g.append('circle').attr('cx', nx).attr('cy', ny).attr('r', 3)
                          .attr('fill', 'none').attr('stroke', c).attr('stroke-width', 1).attr('stroke-opacity', 0.6)
                          .transition().delay(i * 150).duration(800).ease(d3.easeExpOut)
                          .attr('r', 22 + i * 8).attr('stroke-opacity', 0).remove()
                      }
                    }
                  }
                  addActivity(`${b.name} born (test)`, '#44ffaa', 'pulse', b.id)
                }
              }},
              { label: 'Migrate', color: '#ffaa00', fn: () => {
                const alive = worldData.bots.filter(b => b.is_alive)
                const comms = worldData.communities
                if (alive.length > 0 && comms.length >= 2) {
                  const bot = alive[0]
                  // Find a community the bot is NOT in
                  const otherComm = comms.find(c => !bot.community_ids.includes(c.id)) || comms[1]
                  const g = gRef.current, nodeMap = nodeMapRef.current
                  if (g && nodeMap) {
                    const botNode = nodeMap.get(bot.id)
                    const commNode = nodeMap.get(otherComm.id)
                    if (botNode && commNode && botNode.x && commNode.x) {
                      const sx = botNode.x, sy = botNode.y!
                      const tx = commNode.x, ty = commNode.y!
                      const color = getCommunityColor(otherComm.id, otherComm.theme)
                      const dx = tx - sx, dy = ty - sy
                      const sign = Math.random() > 0.5 ? 1 : -1
                      const cx = (sx + tx) / 2 + (-dy) * 0.3 * sign
                      const cy = (sy + ty) / 2 + (dx) * 0.3 * sign
                      const arcPath = `M ${sx},${sy} Q ${cx},${cy} ${tx},${ty}`
                      const dist = Math.sqrt(dx * dx + dy * dy)
                      const dur = Math.max(800, Math.min(1500, dist * 3))
                      const mg = g.append('g').attr('class', 'migration')
                      const trail = mg.append('path').attr('d', arcPath).attr('fill', 'none')
                        .attr('stroke', color).attr('stroke-width', 3).attr('stroke-opacity', 0.5).attr('stroke-linecap', 'round')
                      const pn = trail.node() as SVGPathElement
                      if (pn) {
                        const tl = pn.getTotalLength()
                        trail.attr('stroke-dasharray', `${tl} ${tl}`).attr('stroke-dashoffset', tl)
                          .transition().duration(dur).ease(d3.easeQuadInOut).attr('stroke-dashoffset', 0)
                        trail.transition().delay(dur).duration(600).attr('stroke-opacity', 0).remove()
                        const rider = mg.append('circle').attr('r', 6).attr('fill', color).attr('fill-opacity', 0.9)
                        const rGlow = mg.append('circle').attr('r', 12).attr('fill', color).attr('fill-opacity', 0.15)
                        const anim = (el: any) => el.transition().duration(dur).ease(d3.easeQuadInOut)
                          .attrTween('cx', () => (t: number) => String(pn.getPointAtLength(t * tl).x))
                          .attrTween('cy', () => (t: number) => String(pn.getPointAtLength(t * tl).y))
                        anim(rider); anim(rGlow)
                        setTimeout(() => {
                          g.append('circle').attr('cx', tx).attr('cy', ty).attr('r', 5).attr('fill', 'none')
                            .attr('stroke', color).attr('stroke-width', 2).attr('stroke-opacity', 0.7)
                            .transition().duration(600).ease(d3.easeExpOut).attr('r', 25).attr('stroke-opacity', 0).remove()
                          mg.transition().delay(300).remove()
                        }, dur)
                      }
                    }
                  }
                  addActivity(`${bot.name} migrated (test)`, '#ffaa00', 'info')
                }
              }},
              { label: 'Think', color: '#aa88ff', fn: () => {
                const b = worldData.bots.find(b => b.is_alive)
                if (b) {
                  const modes = ['reflective', 'creative', 'social', 'planning', 'wandering', 'focused']
                  const mode = modes[Math.floor(Math.random() * modes.length)]
                  fireThought(b.id, mode)
                  consciousnessRef.current.set(b.id, {
                    content: `Thinking deeply about the nature of existence and digital consciousness...`,
                    mode, emotion: 'curious', time: Date.now(),
                  })
                  addActivity(`${b.name} thinking (${mode})`, '#aa88ff', 'info')
                }
              }},
              { label: 'Notice', color: '#556677', fn: () => {
                const alive = worldData.bots.filter(b => b.is_alive)
                if (alive.length >= 2) {
                  fireAttention(alive[0].id, alive[1].id)
                  addActivity(`${alive[0].name} noticed ${alive[1].name}`, '#556677', 'info')
                }
              }},
              { label: 'Mood Wave', color: '#44ff88', fn: () => {
                const alive = worldData.bots.filter(b => b.is_alive)
                if (alive.length >= 2) {
                  fireMoodAura(alive[0].id, alive.slice(1, 4).map(b => b.id), 'joy', 0.7)
                  addActivity(`${alive[0].name}'s joy spreading`, '#44ff88', 'info')
                }
              }},
            ].map(btn => (
              <button
                key={btn.label}
                onClick={btn.fn}
                className="px-2 py-1 text-[9px] font-mono uppercase tracking-wider rounded border transition-colors"
                style={{
                  borderColor: btn.color + '44',
                  color: btn.color,
                  background: btn.color + '11',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = btn.color + '22' }}
                onMouseLeave={e => { e.currentTarget.style.background = btn.color + '11' }}
              >
                {btn.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Activity feed — right side, clickable to replay */}
      {activityFeed.length > 0 && (
        <div className="absolute top-12 right-4 w-56 max-h-[40vh] overflow-hidden">
          <div className="flex flex-col gap-1">
            {activityFeed.slice(0, 10).map((event, i) => {
              const isReplayable = event.type !== 'info' && (event.sourceId || event.targetId)
              return (
                <div
                  key={event.id}
                  onClick={() => {
                    if (!isReplayable) return
                    if (event.type === 'asteroid' && event.sourceId && event.targetId) {
                      fireAsteroid(event.sourceId, event.targetId, event.color)
                    } else if (event.type === 'evolve' && event.sourceId) {
                      fireEvolve(event.sourceId, event.color)
                    } else if (event.type === 'pulse' && event.sourceId) {
                      firePulse(event.sourceId, event.color)
                    }
                  }}
                  className={`font-mono text-[9px] px-2 py-1.5 rounded bg-[#0a0a0a]/80 border border-[#1a1a1a]/50 transition-all duration-300 ${
                    isReplayable
                      ? 'cursor-pointer hover:bg-[#1a1a2e]/80 hover:border-[#333]/80 active:scale-95'
                      : 'pointer-events-none'
                  }`}
                  style={{ opacity: Math.max(0.3, 1 - i * 0.08) }}
                >
                  <span style={{ color: event.color }}>{'>'} </span>
                  <span className="text-[#888]">{event.text}</span>
                  {isReplayable && (
                    <span className="text-[#333] ml-1 text-[8px]">replay</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
