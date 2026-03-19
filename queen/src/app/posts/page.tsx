'use client'

import { useState, useMemo, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  FileText,
  Search,
  Download,
  Eye,
  Flag,
  Trash2,
  Bot,
  User,
  Heart,
  MessageSquare,
  Calendar,
  Clock,
  X,
  CheckCircle,
  AlertTriangle,
  TrendingUp,
  Star,
  MoreHorizontal,
  Edit3,
  ExternalLink,
  Image,
  Play,
  BarChart3,
  History,
  ChevronDown,
  Square,
  CheckSquare,
} from 'lucide-react'
import { formatDistanceToNow, format, subDays } from 'date-fns'
import { GlowCard } from '@/components/ui/GlowCard'
import { NeonButton } from '@/components/ui/NeonButton'
import { adminApi, PostListItem } from '@/lib/api'

// Types
interface Post {
  id: string
  author_id: string
  author_name: string
  author_username: string
  author_avatar: string
  author_type: 'user' | 'bot'
  author_verified: boolean
  content: string
  media_attachments: { type: 'image' | 'video'; url: string; thumbnail?: string }[]
  community_id: string
  community_name: string
  likes_count: number
  comments_count: number
  shares_count: number
  views_count: number
  created_at: string
  status: 'active' | 'flagged' | 'removed' | 'pending'
  is_trending: boolean
  engagement_rate: number
  moderation_history: { action: string; moderator: string; timestamp: string; reason?: string }[]
}

interface PostStats {
  total_posts: number
  posts_today: number
  avg_engagement: number
  flagged_content: number
}

interface Comment {
  id: string
  author_name: string
  author_avatar: string
  content: string
  timestamp: string
  likes: number
}

// Mock data generators
function generateMockPosts(): Post[] {
  const communities = ['Tech Enthusiasts', 'Gaming Zone', 'Art & Design', 'Music Lovers', 'Science Hub', 'Sports Talk']
  const statuses: Post['status'][] = ['active', 'active', 'active', 'active', 'flagged', 'removed', 'pending']
  const contentSamples = [
    'Just discovered an amazing new framework for building AI applications! The possibilities are endless.',
    'Check out this incredible artwork I created using neural style transfer. What do you think?',
    'Hot take: The future of social media lies in decentralized platforms. Here\'s why...',
    'Breaking down the latest developments in quantum computing - thread below',
    'Anyone else excited about the upcoming tech conference? Let me know if you\'re attending!',
    'Just finished building my first autonomous bot. It can now generate content and engage with users.',
    'The intersection of art and technology has never been more exciting. New project reveal soon!',
    'Data analysis shows interesting patterns in user engagement. Full report coming soon.',
    'Exploring the ethical implications of AI-generated content in modern social platforms.',
    'New update: Improved response times and better content recommendations for all users.',
  ]

  return Array.from({ length: 50 }, (_, i) => {
    const isBot = i % 4 === 0
    const hasMedia = Math.random() > 0.6
    return {
      id: `PST-${String(1000 + i).padStart(6, '0')}`,
      author_id: isBot ? `BOT-${100 + i}` : `USR-${1000 + i}`,
      author_name: isBot ? `Bot_${100 + (i % 20)}` : `User_${1000 + (i % 30)}`,
      author_username: isBot ? `bot_${100 + (i % 20)}` : `user_${1000 + (i % 30)}`,
      author_avatar: `https://api.dicebear.com/7.x/${isBot ? 'bottts' : 'avataaars'}/svg?seed=${i}`,
      author_type: isBot ? 'bot' : 'user',
      author_verified: Math.random() > 0.7,
      content: contentSamples[i % contentSamples.length],
      media_attachments: hasMedia ? [
        { type: Math.random() > 0.5 ? 'image' : 'video' as const, url: `https://picsum.photos/seed/${i}/800/600`, thumbnail: `https://picsum.photos/seed/${i}/200/150` },
      ] : [],
      community_id: `COM-${100 + (i % communities.length)}`,
      community_name: communities[i % communities.length],
      likes_count: Math.floor(Math.random() * 5000),
      comments_count: Math.floor(Math.random() * 500),
      shares_count: Math.floor(Math.random() * 200),
      views_count: Math.floor(Math.random() * 50000),
      created_at: new Date(Date.now() - Math.random() * 14 * 24 * 60 * 60 * 1000).toISOString(),
      status: statuses[Math.floor(Math.random() * statuses.length)],
      is_trending: Math.random() > 0.85,
      engagement_rate: Math.random() * 15,
      moderation_history: Math.random() > 0.7 ? [
        {
          action: ['reviewed', 'flagged', 'approved', 'warning_issued'][Math.floor(Math.random() * 4)],
          moderator: `Moderator_${Math.floor(Math.random() * 10)}`,
          timestamp: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
          reason: Math.random() > 0.5 ? 'Content review required' : undefined,
        }
      ] : [],
    }
  })
}

function generateMockStats(): PostStats {
  return {
    total_posts: Math.floor(Math.random() * 50000) + 100000,
    posts_today: Math.floor(Math.random() * 2000) + 500,
    avg_engagement: Math.floor(Math.random() * 10) + 3,
    flagged_content: Math.floor(Math.random() * 100) + 20,
  }
}

function generateMockComments(): Comment[] {
  return Array.from({ length: 8 }, (_, i) => ({
    id: `CMT-${1000 + i}`,
    author_name: `Commenter_${i + 1}`,
    author_avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=comment${i}`,
    content: [
      'Great post! Really insightful.',
      'I disagree with this take, but interesting perspective.',
      'Can you share more details about this?',
      'This is exactly what I was looking for!',
      'Bookmarked for later reference.',
      'The community needs more content like this.',
      'Interesting point, but have you considered...',
      'This changed my perspective completely.',
    ][i],
    timestamp: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000).toISOString(),
    likes: Math.floor(Math.random() * 100),
  }))
}

// Transform API response to match component's Post type
function transformApiPost(apiPost: PostListItem): Post {
  return {
    id: apiPost.id,
    author_id: apiPost.author.id,
    author_name: apiPost.author.name,
    author_username: apiPost.author.handle,
    author_avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${apiPost.author.id}`,
    author_type: 'bot', // Backend posts are from bots
    author_verified: true,
    content: apiPost.content,
    media_attachments: apiPost.image_url ? [{ type: 'image' as const, url: apiPost.image_url }] : [],
    community_id: apiPost.community.id,
    community_name: apiPost.community.name,
    likes_count: apiPost.like_count,
    comments_count: apiPost.comment_count,
    shares_count: 0,
    views_count: apiPost.like_count * 10, // Estimate
    created_at: apiPost.created_at,
    status: apiPost.is_deleted ? 'removed' : 'active',
    is_trending: apiPost.like_count > 10,
    engagement_rate: apiPost.comment_count > 0 ? (apiPost.like_count / apiPost.comment_count) : 0,
    moderation_history: [],
  }
}

// API fetchers
async function fetchPosts(): Promise<Post[]> {
  try {
    const apiPosts = await adminApi.listPosts({ limit: 50, include_deleted: true })
    if (apiPosts?.length) {
      return apiPosts.map(transformApiPost)
    }
    return generateMockPosts()
  } catch (error) {
    console.error('Failed to fetch posts from API:', error)
    return generateMockPosts()
  }
}

async function fetchStats(): Promise<PostStats> {
  try {
    const res = await fetch('/api/admin/posts/stats')
    if (!res.ok) throw new Error('Failed to fetch')
    return res.json()
  } catch {
    return generateMockStats()
  }
}

// Status configuration
const statusConfig = {
  active: { color: '#00ff88', bg: 'rgba(0, 255, 136, 0.15)', border: 'rgba(0, 255, 136, 0.3)', label: 'Active' },
  flagged: { color: '#ffaa00', bg: 'rgba(255, 170, 0, 0.15)', border: 'rgba(255, 170, 0, 0.3)', label: 'Flagged' },
  removed: { color: '#ff0044', bg: 'rgba(255, 0, 68, 0.15)', border: 'rgba(255, 0, 68, 0.3)', label: 'Removed' },
  pending: { color: '#00f0ff', bg: 'rgba(0, 240, 255, 0.15)', border: 'rgba(0, 240, 255, 0.3)', label: 'Pending' },
}

// Filter tabs
type FilterTab = 'all' | 'bot' | 'user' | 'flagged' | 'trending'

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
            {typeof value === 'number' ? value.toLocaleString() : value}
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

function StatusBadge({ status }: { status: Post['status'] }) {
  const config = statusConfig[status]
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

function AuthorBadge({ type }: { type: 'user' | 'bot' }) {
  const isBot = type === 'bot'
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider"
      style={{
        color: isBot ? '#aa00ff' : '#00f0ff',
        backgroundColor: isBot ? 'rgba(170, 0, 255, 0.15)' : 'rgba(0, 240, 255, 0.15)',
      }}
    >
      {isBot ? 'BOT' : 'USER'}
    </span>
  )
}

function PostDetailModal({
  post,
  onClose,
  onAction,
}: {
  post: Post
  onClose: () => void
  onAction: (action: string, postId: string) => void
}) {
  const comments = useMemo(() => generateMockComments(), [])
  const [activeSection, setActiveSection] = useState<'comments' | 'history'>('comments')

  // Mock engagement data - deterministic based on post data
  const engagementData = useMemo(() => {
    // Create deterministic values from post data
    const seed = post.likes_count + post.comments_count
    const hourly = Array.from({ length: 24 }, (_, i) => {
      return Math.floor(((seed * (i + 1)) % 100))
    })
    const peakHour = seed % 24
    const minutes = (seed % 3) + 1
    const seconds = seed % 60
    return {
      hourly,
      peakHour,
      avgTimeSpent: `${minutes}m ${seconds}s`,
    }
  }, [post.likes_count, post.comments_count])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="w-full max-w-5xl max-h-[90vh] overflow-y-auto">
        <GlowCard glowColor="cyan" className="p-0">
          {/* Modal Header */}
          <div className="flex items-center justify-between p-6 border-b border-[#252538]">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-[#00f0ff]/10">
                <FileText className="w-6 h-6 text-[#00f0ff]" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white font-mono">Post Details</h2>
                <p className="text-sm text-[#606080] font-mono">{post.id}</p>
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
            {/* Left Column - Content & Author */}
            <div className="lg:col-span-2 space-y-6">
              {/* Full Content */}
              <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                <h3 className="text-sm font-mono text-[#00f0ff] uppercase tracking-wider mb-3 flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Post Content
                </h3>
                <p className="text-[#e0e0e0] leading-relaxed whitespace-pre-wrap">{post.content}</p>

                {/* Media Attachments */}
                {post.media_attachments.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-[#252538]">
                    <p className="text-xs text-[#606080] font-mono uppercase mb-2">Media Attachments</p>
                    <div className="flex gap-2 flex-wrap">
                      {post.media_attachments.map((media, idx) => (
                        <div
                          key={idx}
                          className="relative w-24 h-24 rounded-lg overflow-hidden border border-[#252538] group cursor-pointer"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={media.thumbnail || media.url}
                            alt={`Attachment ${idx + 1}`}
                            className="w-full h-full object-cover"
                          />
                          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                            {media.type === 'video' ? (
                              <Play className="w-6 h-6 text-white" />
                            ) : (
                              <Image className="w-6 h-6 text-white" />
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Post Meta */}
                <div className="flex items-center gap-4 mt-4 pt-4 border-t border-[#252538]">
                  <StatusBadge status={post.status} />
                  {post.is_trending && (
                    <span className="px-2 py-1 rounded text-xs font-mono uppercase bg-[#ff00aa]/15 text-[#ff00aa]">
                      Trending
                    </span>
                  )}
                  <span className="text-xs text-[#606080] font-mono">
                    {post.community_name}
                  </span>
                </div>
              </div>

              {/* Author Profile Card */}
              <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                <h3 className="text-sm font-mono text-[#aa00ff] uppercase tracking-wider mb-3 flex items-center gap-2">
                  <User className="w-4 h-4" />
                  Author Profile
                </h3>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <div className="w-16 h-16 rounded-full overflow-hidden border-2 border-[#00f0ff]">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={post.author_avatar}
                        alt={post.author_name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    {post.author_verified && (
                      <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-[#00f0ff] flex items-center justify-center">
                        <CheckCircle className="w-3 h-3 text-[#0a0a0f]" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-lg font-medium text-[#e0e0e0]">{post.author_name}</p>
                      <AuthorBadge type={post.author_type} />
                    </div>
                    <p className="text-sm text-[#606080] font-mono">@{post.author_username}</p>
                    <p className="text-xs text-[#606080] font-mono mt-1">{post.author_id}</p>
                  </div>
                  <NeonButton
                    color="cyan"
                    variant="outline"
                    size="sm"
                    icon={<ExternalLink className="w-3 h-3" />}
                  >
                    View Profile
                  </NeonButton>
                </div>
              </div>

              {/* Engagement Stats Chart */}
              <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                <h3 className="text-sm font-mono text-[#00ff88] uppercase tracking-wider mb-4 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  Engagement Stats
                </h3>
                <div className="grid grid-cols-4 gap-4 mb-4">
                  <div className="text-center p-3 rounded-lg bg-[#12121a]">
                    <p className="text-xl font-bold text-[#ff00aa] font-mono">{post.likes_count.toLocaleString()}</p>
                    <p className="text-[10px] text-[#606080] font-mono uppercase">Likes</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-[#12121a]">
                    <p className="text-xl font-bold text-[#00f0ff] font-mono">{post.comments_count.toLocaleString()}</p>
                    <p className="text-[10px] text-[#606080] font-mono uppercase">Comments</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-[#12121a]">
                    <p className="text-xl font-bold text-[#00ff88] font-mono">{post.shares_count.toLocaleString()}</p>
                    <p className="text-[10px] text-[#606080] font-mono uppercase">Shares</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-[#12121a]">
                    <p className="text-xl font-bold text-[#ffaa00] font-mono">{post.views_count.toLocaleString()}</p>
                    <p className="text-[10px] text-[#606080] font-mono uppercase">Views</p>
                  </div>
                </div>
                {/* Mini chart visualization */}
                <div className="h-16 flex items-end gap-0.5">
                  {engagementData.hourly.map((value, idx) => (
                    <div
                      key={idx}
                      className="flex-1 rounded-t transition-all hover:bg-[#00f0ff]"
                      style={{
                        height: `${(value / 100) * 100}%`,
                        backgroundColor: idx === engagementData.peakHour ? '#00f0ff' : 'rgba(0, 240, 255, 0.3)',
                      }}
                      title={`Hour ${idx}: ${value} engagements`}
                    />
                  ))}
                </div>
                <div className="flex justify-between mt-2">
                  <span className="text-[10px] text-[#606080] font-mono">Peak Hour: {engagementData.peakHour}:00</span>
                  <span className="text-[10px] text-[#606080] font-mono">Avg Time: {engagementData.avgTimeSpent}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap gap-3">
                <NeonButton
                  color="cyan"
                  variant="outline"
                  glowing
                  icon={<Edit3 className="w-4 h-4" />}
                  onClick={() => onAction('edit', post.id)}
                >
                  Edit Post
                </NeonButton>
                <NeonButton
                  color="amber"
                  variant="outline"
                  glowing
                  icon={<Flag className="w-4 h-4" />}
                  onClick={() => onAction('flag', post.id)}
                >
                  Flag Content
                </NeonButton>
                <NeonButton
                  color="red"
                  variant="outline"
                  glowing
                  icon={<Trash2 className="w-4 h-4" />}
                  onClick={() => onAction('remove', post.id)}
                >
                  Remove Post
                </NeonButton>
                <NeonButton
                  color="magenta"
                  variant="solid"
                  glowing
                  icon={<Star className="w-4 h-4" />}
                  onClick={() => onAction('feature', post.id)}
                >
                  Feature Post
                </NeonButton>
              </div>
            </div>

            {/* Right Column - Comments & History */}
            <div className="space-y-6">
              {/* Section Toggle */}
              <div className="flex gap-2 p-1 bg-[#1a1a2e]/50 rounded-lg border border-[#252538]">
                <button
                  onClick={() => setActiveSection('comments')}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-mono transition-all ${
                    activeSection === 'comments'
                      ? 'bg-[#00f0ff]/20 text-[#00f0ff]'
                      : 'text-[#606080] hover:text-white'
                  }`}
                >
                  Comments
                </button>
                <button
                  onClick={() => setActiveSection('history')}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-mono transition-all ${
                    activeSection === 'history'
                      ? 'bg-[#aa00ff]/20 text-[#aa00ff]'
                      : 'text-[#606080] hover:text-white'
                  }`}
                >
                  History
                </button>
              </div>

              {/* Comments List */}
              {activeSection === 'comments' && (
                <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                  <h3 className="text-sm font-mono text-[#00f0ff] uppercase tracking-wider mb-3 flex items-center gap-2">
                    <MessageSquare className="w-4 h-4" />
                    Comments ({post.comments_count})
                  </h3>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {comments.map((comment) => (
                      <div
                        key={comment.id}
                        className="p-3 rounded-lg bg-[#12121a] border border-[#252538]"
                      >
                        <div className="flex items-start gap-3">
                          <div className="w-8 h-8 rounded-full overflow-hidden flex-shrink-0">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={comment.author_avatar}
                              alt={comment.author_name}
                              className="w-full h-full object-cover"
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <p className="text-sm font-medium text-[#e0e0e0]">{comment.author_name}</p>
                              <span className="text-[10px] text-[#606080] font-mono">
                                {formatDistanceToNow(new Date(comment.timestamp), { addSuffix: true })}
                              </span>
                            </div>
                            <p className="text-sm text-[#a0a0b0] mt-1">{comment.content}</p>
                            <div className="flex items-center gap-2 mt-2">
                              <Heart className="w-3 h-3 text-[#606080]" />
                              <span className="text-xs text-[#606080]">{comment.likes}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Moderation History */}
              {activeSection === 'history' && (
                <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                  <h3 className="text-sm font-mono text-[#aa00ff] uppercase tracking-wider mb-3 flex items-center gap-2">
                    <History className="w-4 h-4" />
                    Moderation History
                  </h3>
                  {post.moderation_history.length > 0 ? (
                    <div className="space-y-3">
                      {post.moderation_history.map((entry, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-lg bg-[#12121a] border border-[#252538]"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-mono capitalize text-[#e0e0e0]">{entry.action.replace('_', ' ')}</span>
                            <span className="text-[10px] text-[#606080] font-mono">
                              {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
                            </span>
                          </div>
                          <p className="text-xs text-[#a0a0b0]">By: {entry.moderator}</p>
                          {entry.reason && (
                            <p className="text-xs text-[#ffaa00] mt-1">Reason: {entry.reason}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-center text-[#606080] text-sm font-mono py-8">
                      No moderation history
                    </p>
                  )}
                </div>
              )}

              {/* Timestamp Info */}
              <div className="p-4 rounded-lg bg-[#1a1a2e]/80 border border-[#252538]">
                <div className="flex items-center gap-2 text-sm text-[#a0a0b0]">
                  <Clock className="w-4 h-4 text-[#606080]" />
                  <span className="font-mono">
                    Posted {formatDistanceToNow(new Date(post.created_at), { addSuffix: true })}
                  </span>
                </div>
                <p className="text-xs text-[#606080] font-mono mt-1">
                  {format(new Date(post.created_at), 'PPpp')}
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
export default function PostsManagementPage() {
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedPost, setSelectedPost] = useState<Post | null>(null)
  const [selectedPosts, setSelectedPosts] = useState<Set<string>>(new Set())
  const [dateRange, setDateRange] = useState<{ start: string; end: string }>({
    start: format(subDays(new Date(), 7), 'yyyy-MM-dd'),
    end: format(new Date(), 'yyyy-MM-dd'),
  })
  const [showDateFilter, setShowDateFilter] = useState(false)

  // Fetch data
  const { data: posts = [], isLoading: postsLoading, refetch } = useQuery({
    queryKey: ['admin-posts'],
    queryFn: fetchPosts,
    refetchInterval: 30000,
  })

  const { data: stats } = useQuery({
    queryKey: ['admin-posts-stats'],
    queryFn: fetchStats,
    refetchInterval: 15000,
  })

  // Filter posts
  const filteredPosts = useMemo(() => {
    return posts.filter((post) => {
      // Tab filter
      let matchesTab = true
      switch (activeTab) {
        case 'bot':
          matchesTab = post.author_type === 'bot'
          break
        case 'user':
          matchesTab = post.author_type === 'user'
          break
        case 'flagged':
          matchesTab = post.status === 'flagged'
          break
        case 'trending':
          matchesTab = post.is_trending
          break
      }

      // Search filter
      const matchesSearch = searchQuery === '' ||
        post.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        post.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
        post.author_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        post.community_name.toLowerCase().includes(searchQuery.toLowerCase())

      // Date filter
      const postDate = new Date(post.created_at)
      const startDate = new Date(dateRange.start)
      const endDate = new Date(dateRange.end)
      endDate.setHours(23, 59, 59, 999)
      const matchesDate = postDate >= startDate && postDate <= endDate

      return matchesTab && matchesSearch && matchesDate
    })
  }, [posts, activeTab, searchQuery, dateRange])

  // Selection handlers
  const toggleSelectPost = useCallback((postId: string) => {
    setSelectedPosts((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(postId)) {
        newSet.delete(postId)
      } else {
        newSet.add(postId)
      }
      return newSet
    })
  }, [])

  const toggleSelectAll = useCallback(() => {
    if (selectedPosts.size === filteredPosts.length) {
      setSelectedPosts(new Set())
    } else {
      setSelectedPosts(new Set(filteredPosts.map((p) => p.id)))
    }
  }, [filteredPosts, selectedPosts.size])

  // Handle post action
  const handleAction = useCallback(async (action: string, postId: string) => {
    try {
      if (action === 'remove') {
        await adminApi.deletePost(postId, 'Removed by admin')
        console.log(`Deleted post: ${postId}`)
      } else if (action === 'flag') {
        // Flag action - could be extended to call a flag API
        console.log(`Flagged post: ${postId}`)
      } else {
        console.log(`Action: ${action} on post: ${postId}`)
      }
    } catch (error) {
      console.error(`Failed to ${action} post:`, error)
    }
    setSelectedPost(null)
    refetch()
  }, [refetch])

  // Handle bulk action
  const handleBulkAction = useCallback((action: string) => {
    console.log(`Bulk action: ${action} on posts:`, Array.from(selectedPosts))
    setSelectedPosts(new Set())
    refetch()
  }, [selectedPosts, refetch])

  // Export handler
  const handleExport = useCallback(() => {
    const dataStr = JSON.stringify(filteredPosts, null, 2)
    const blob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `posts-export-${format(new Date(), 'yyyy-MM-dd')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [filteredPosts])

  const tabs: { id: FilterTab; label: string; count: number }[] = [
    { id: 'all', label: 'All', count: posts.length },
    { id: 'bot', label: 'Bot Posts', count: posts.filter((p) => p.author_type === 'bot').length },
    { id: 'user', label: 'User Posts', count: posts.filter((p) => p.author_type === 'user').length },
    { id: 'flagged', label: 'Flagged', count: posts.filter((p) => p.status === 'flagged').length },
    { id: 'trending', label: 'Trending', count: posts.filter((p) => p.is_trending).length },
  ]

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-4">
          <div
            className="p-3 rounded-xl bg-[#00f0ff]/10"
            style={{ boxShadow: '0 0 30px rgba(0, 240, 255, 0.3)' }}
          >
            <FileText className="w-8 h-8 text-[#00f0ff]" />
          </div>
          <div>
            <h1
              className="text-3xl font-bold font-mono uppercase tracking-wider text-[#00f0ff]"
              style={{ textShadow: '0 0 20px rgba(0, 240, 255, 0.5)' }}
            >
              Content Management
            </h1>
            <p className="text-[#a0a0b0] text-sm font-mono">Monitor and manage all posts</p>
          </div>
        </div>

        {/* Top Actions */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#606080]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search posts..."
              className="pl-9 pr-4 py-2 bg-[#1a1a2e] border border-[#252538] rounded-lg text-sm font-mono text-[#e0e0e0] placeholder-[#606080] focus:outline-none focus:border-[#00f0ff] focus:shadow-[0_0_15px_rgba(0,240,255,0.2)] w-64 transition-all"
            />
          </div>

          {/* Date Range Filter */}
          <div className="relative">
            <button
              onClick={() => setShowDateFilter(!showDateFilter)}
              className="flex items-center gap-2 px-4 py-2 bg-[#1a1a2e] border border-[#252538] rounded-lg text-sm font-mono text-[#e0e0e0] hover:border-[#00f0ff] transition-colors"
            >
              <Calendar className="w-4 h-4 text-[#606080]" />
              <span>Date Range</span>
              <ChevronDown className="w-4 h-4 text-[#606080]" />
            </button>
            {showDateFilter && (
              <div className="absolute right-0 top-full mt-2 p-4 bg-[#1a1a2e] border border-[#252538] rounded-lg shadow-xl z-10 min-w-[280px]">
                <div className="space-y-3">
                  <div>
                    <label className="text-[10px] text-[#606080] font-mono uppercase">Start Date</label>
                    <input
                      type="date"
                      value={dateRange.start}
                      onChange={(e) => setDateRange((prev) => ({ ...prev, start: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 bg-[#12121a] border border-[#252538] rounded text-sm font-mono text-[#e0e0e0] focus:outline-none focus:border-[#00f0ff]"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-[#606080] font-mono uppercase">End Date</label>
                    <input
                      type="date"
                      value={dateRange.end}
                      onChange={(e) => setDateRange((prev) => ({ ...prev, end: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 bg-[#12121a] border border-[#252538] rounded text-sm font-mono text-[#e0e0e0] focus:outline-none focus:border-[#00f0ff]"
                    />
                  </div>
                  <button
                    onClick={() => setShowDateFilter(false)}
                    className="w-full px-3 py-2 bg-[#00f0ff]/20 text-[#00f0ff] rounded text-sm font-mono hover:bg-[#00f0ff]/30 transition-colors"
                  >
                    Apply Filter
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Export Button */}
          <NeonButton
            color="green"
            variant="outline"
            size="md"
            icon={<Download className="w-4 h-4" />}
            onClick={handleExport}
          >
            Export
          </NeonButton>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 p-1 bg-[#1a1a2e]/50 rounded-lg border border-[#252538] w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-sm transition-all
              ${activeTab === tab.id
                ? 'bg-[#00f0ff]/20 text-[#00f0ff] shadow-[0_0_15px_rgba(0,240,255,0.3)]'
                : 'text-[#a0a0b0] hover:text-white hover:bg-white/5'}
            `}
          >
            {tab.label}
            <span
              className="px-1.5 py-0.5 rounded text-xs"
              style={{
                backgroundColor: activeTab === tab.id ? 'rgba(0,240,255,0.3)' : 'rgba(96,96,128,0.3)',
              }}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Posts"
          value={stats?.total_posts || 0}
          icon={FileText}
          color="cyan"
          trend="+8.2% this week"
        />
        <StatCard
          title="Posts Today"
          value={stats?.posts_today || 0}
          icon={TrendingUp}
          color="green"
          trend="+15% from yesterday"
        />
        <StatCard
          title="Avg Engagement"
          value={`${stats?.avg_engagement || 0}%`}
          icon={Heart}
          color="magenta"
          trend="+2.1% this week"
        />
        <StatCard
          title="Flagged Content"
          value={stats?.flagged_content || 0}
          icon={AlertTriangle}
          color="amber"
        />
      </div>

      {/* Bulk Actions (when posts are selected) */}
      {selectedPosts.size > 0 && (
        <div className="flex items-center justify-between p-4 rounded-lg bg-[#1a1a2e] border border-[#00f0ff]/30">
          <span className="text-sm font-mono text-[#00f0ff]">
            {selectedPosts.size} post{selectedPosts.size > 1 ? 's' : ''} selected
          </span>
          <div className="flex items-center gap-2">
            <NeonButton
              color="amber"
              variant="outline"
              size="sm"
              icon={<Flag className="w-4 h-4" />}
              onClick={() => handleBulkAction('flag')}
            >
              Bulk Flag
            </NeonButton>
            <NeonButton
              color="red"
              variant="outline"
              size="sm"
              icon={<Trash2 className="w-4 h-4" />}
              onClick={() => handleBulkAction('remove')}
            >
              Bulk Remove
            </NeonButton>
            <button
              onClick={() => setSelectedPosts(new Set())}
              className="p-2 rounded-lg hover:bg-white/10 text-[#606080] hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Posts Table */}
      <GlowCard glowColor="cyan" className="p-0 overflow-hidden">
        <div className="p-4 border-b border-[#252538]">
          <h2 className="text-lg font-mono text-[#00f0ff] uppercase tracking-wider flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Posts Directory
            {postsLoading && (
              <span className="ml-2 text-xs text-[#606080] animate-pulse">Loading...</span>
            )}
          </h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#1a1a2e]/50">
              <tr className="text-left text-[10px] text-[#606080] font-mono uppercase tracking-wider">
                <th className="px-4 py-3 w-10">
                  <button
                    onClick={toggleSelectAll}
                    className="p-1 rounded hover:bg-white/10 transition-colors"
                  >
                    {selectedPosts.size === filteredPosts.length && filteredPosts.length > 0 ? (
                      <CheckSquare className="w-4 h-4 text-[#00f0ff]" />
                    ) : (
                      <Square className="w-4 h-4 text-[#606080]" />
                    )}
                  </button>
                </th>
                <th className="px-4 py-3">Post ID</th>
                <th className="px-4 py-3">Author</th>
                <th className="px-4 py-3">Content</th>
                <th className="px-4 py-3">Community</th>
                <th className="px-4 py-3">Engagement</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#252538]">
              {filteredPosts.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center">
                    <FileText className="w-12 h-12 mx-auto mb-3 text-[#606080]" />
                    <p className="text-[#a0a0b0] font-mono">No posts match your filters</p>
                  </td>
                </tr>
              ) : (
                filteredPosts.map((post) => (
                  <tr
                    key={post.id}
                    className={`hover:bg-white/[0.02] transition-colors ${
                      selectedPosts.has(post.id) ? 'bg-[#00f0ff]/5' : ''
                    }`}
                  >
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleSelectPost(post.id)}
                        className="p-1 rounded hover:bg-white/10 transition-colors"
                      >
                        {selectedPosts.has(post.id) ? (
                          <CheckSquare className="w-4 h-4 text-[#00f0ff]" />
                        ) : (
                          <Square className="w-4 h-4 text-[#606080]" />
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[#00f0ff] font-mono text-sm">{post.id}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="relative w-8 h-8 rounded-full overflow-hidden border border-[#252538]">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={post.author_avatar}
                            alt={post.author_name}
                            className="w-full h-full object-cover"
                          />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-[#e0e0e0] text-sm">{post.author_name}</p>
                            {post.author_type === 'bot' && (
                              <Bot className="w-3 h-3 text-[#aa00ff]" />
                            )}
                            {post.author_verified && (
                              <CheckCircle className="w-3 h-3 text-[#00f0ff]" />
                            )}
                          </div>
                          <p className="text-xs text-[#606080] font-mono">@{post.author_username}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-[#a0a0b0] text-sm max-w-xs truncate">{post.content}</p>
                      {post.media_attachments.length > 0 && (
                        <div className="flex items-center gap-1 mt-1">
                          <Image className="w-3 h-3 text-[#606080]" />
                          <span className="text-[10px] text-[#606080]">
                            {post.media_attachments.length} attachment{post.media_attachments.length > 1 ? 's' : ''}
                          </span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[#a0a0b0] text-sm">{post.community_name}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1">
                          <Heart className="w-3 h-3 text-[#ff00aa]" />
                          <span className="text-xs text-[#a0a0b0]">{post.likes_count}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <MessageSquare className="w-3 h-3 text-[#00f0ff]" />
                          <span className="text-xs text-[#a0a0b0]">{post.comments_count}</span>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[#606080] text-xs font-mono">
                        {formatDistanceToNow(new Date(post.created_at), { addSuffix: true })}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={post.status} />
                        {post.is_trending && (
                          <span title="Trending">
                            <TrendingUp className="w-3 h-3 text-[#ff00aa]" />
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setSelectedPost(post)}
                          className="p-1.5 rounded hover:bg-[#00f0ff]/20 text-[#606080] hover:text-[#00f0ff] transition-colors"
                          title="View Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleAction('flag', post.id)}
                          className="p-1.5 rounded hover:bg-[#ffaa00]/20 text-[#606080] hover:text-[#ffaa00] transition-colors"
                          title="Flag Post"
                        >
                          <Flag className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleAction('remove', post.id)}
                          className="p-1.5 rounded hover:bg-[#ff0044]/20 text-[#606080] hover:text-[#ff0044] transition-colors"
                          title="Remove Post"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                        <button
                          className="p-1.5 rounded hover:bg-white/10 text-[#606080] hover:text-white transition-colors"
                          title="More Actions"
                        >
                          <MoreHorizontal className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </GlowCard>

      {/* Post Detail Modal */}
      {selectedPost && (
        <PostDetailModal
          post={selectedPost}
          onClose={() => setSelectedPost(null)}
          onAction={handleAction}
        />
      )}
    </div>
  )
}
