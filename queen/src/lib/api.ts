/**
 * API Client for Admin Dashboard
 * Connects to the Python backend API
 */

// API Configuration
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Types matching backend response models
export interface DashboardStats {
  total_users: number;
  active_users_24h: number;
  total_bots: number;
  active_bots: number;
  total_posts: number;
  posts_24h: number;
  total_messages: number;
  llm_requests_today: number;
  avg_response_time: number;
  timestamp: string;
}

export interface OverviewMetrics {
  total_users: number;
  new_users_period: number;
  active_users_period: number;
  user_growth_rate: number;
  total_bots: number;
  active_bots: number;
  paused_bots: number;
  total_posts: number;
  new_posts_period: number;
  post_growth_rate: number;
  total_engagement: number;
  avg_engagement_per_post: number;
  engagement_rate: number;
  start_date: string;
  end_date: string;
  granularity: string;
}

export interface EngagementDataPoint {
  timestamp: string;
  label: string;
  likes: number;
  comments: number;
  shares: number;
  total: number;
}

export interface EngagementMetrics {
  data_points: EngagementDataPoint[];
  summary: {
    total_likes: number;
    total_comments: number;
    total_shares: number;
    total_engagement: number;
    avg_likes_per_period: number;
    avg_comments_per_period: number;
  };
  granularity: string;
  start_date: string;
  end_date: string;
}

export interface BotListItem {
  id: string;
  display_name: string;
  handle: string;
  bio: string;
  avatar_seed: string;
  is_active: boolean;
  is_paused: boolean;
  is_deleted: boolean;
  created_at: string;
  last_active: string | null;
  post_count: number;
  comment_count: number;
}

export interface BotDetails {
  id: string;
  display_name: string;
  handle: string;
  bio: string;
  backstory: string;
  avatar_seed: string;
  age: number;
  gender: string;
  location: string;
  interests: string[];
  personality_traits: Record<string, number>;
  writing_fingerprint: Record<string, unknown>;
  activity_pattern: Record<string, unknown>;
  emotional_state: Record<string, unknown>;
  is_active: boolean;
  is_paused: boolean;
  is_deleted: boolean;
  is_ai_labeled: boolean;
  ai_label_text: string;
  created_at: string;
  last_active: string | null;
  paused_at: string | null;
  stats: Record<string, number>;
  recent_posts: Array<Record<string, unknown>>;
  metrics: Record<string, number> | null;
}

export interface UserListItem {
  id: string;
  display_name: string;
  device_id: string;
  avatar_seed: string;
  is_admin: boolean;
  is_banned: boolean;
  created_at: string;
  last_active: string | null;
  like_count: number;
}

export interface UserDetails {
  id: string;
  display_name: string;
  device_id: string;
  avatar_seed: string;
  is_admin: boolean;
  is_banned: boolean;
  ban_reason: string | null;
  banned_at: string | null;
  created_at: string;
  last_active: string | null;
  stats: Record<string, number>;
}

export interface Community {
  id: string;
  name: string;
  description: string;
  theme: string;
  tone: string;
  current_bot_count: number;
  activity_level: number;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  components?: {
    database: string;
    llm: string;
    scheduler: string;
  };
}

export interface EngineStatus {
  status: string;
  uptime_hours: number;
  pending_activities: number;
  running_tasks: number;
  last_error: string | null;
  capacity_used: number;
}

export interface SystemLog {
  id: string;
  level: string;
  source: string;
  message: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface Report {
  id: string;
  content_type: string;
  content_id: string;
  content_text: string;
  flag_reason: string;
  is_system_flagged: boolean;
  status: string;
  created_at: string;
  reviewed_at: string | null;
  action_taken: string | null;
}

export interface PostListItem {
  id: string;
  author: { id: string; name: string; handle: string };
  community: { id: string; name: string };
  content: string;
  image_url: string | null;
  like_count: number;
  comment_count: number;
  is_deleted: boolean;
  created_at: string;
}

export interface BotMetricsItem {
  bot_id: string;
  bot_handle: string;
  bot_name: string;
  avatar_url: string | null;
  posts_created: number;
  comments_created: number;
  chat_messages_sent: number;
  dm_responses: number;
  total_content: number;
  likes_received: number;
  comments_received: number;
  engagement_rate: number;
  is_active: boolean;
  is_paused: boolean;
  last_active: string | null;
}

export interface BotMetricsResponse {
  bots: BotMetricsItem[];
  total_bots: number;
  summary: Record<string, unknown>;
  start_date: string;
  end_date: string;
  granularity: string;
}

export interface HeatmapCell {
  hour: number;
  day_of_week: number;
  day_name: string;
  value: number;
  normalized: number;
}

export interface ActivityHeatmapResponse {
  cells: HeatmapCell[];
  max_value: number;
  total_activity: number;
  peak_hour: number;
  peak_day: number;
  peak_day_name: string;
  metric_type: string;
  days_analyzed: number;
  generated_at: string;
}

export interface SentimentDistribution {
  positive_count: number;
  positive_percentage: number;
  neutral_count: number;
  neutral_percentage: number;
  negative_count: number;
  negative_percentage: number;
  total_analyzed: number;
}

export interface SentimentAnalysisResponse {
  distribution: SentimentDistribution;
  trends: Array<{
    timestamp: string;
    label: string;
    positive: number;
    neutral: number;
    negative: number;
    dominant_sentiment: string;
  }>;
  top_positive: Array<{ content_id: string; content_preview: string; sentiment: string; confidence: number }>;
  top_negative: Array<{ content_id: string; content_preview: string; sentiment: string; confidence: number }>;
  analysis_method: string;
  start_date: string;
  end_date: string;
  content_type: string;
}

export interface UserMetricsItem {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  posts_created: number;
  comments_made: number;
  likes_given: number;
  chat_messages: number;
  dm_messages: number;
  total_activity: number;
  session_count: number;
  total_time_minutes: number;
  avg_session_minutes: number;
  joined_at: string | null;
  last_active: string | null;
}

export interface UserMetricsResponse {
  users: UserMetricsItem[];
  total_users: number;
  active_users_count: number;
  summary: Record<string, unknown>;
  start_date: string;
  end_date: string;
  granularity: string;
}

export interface AuthenticityMode {
  demo_mode: boolean;
  timing_multiplier: number;
  description: string;
}

// Settings Types
export interface GeneralSettings {
  site_name: string;
  site_description: string;
  maintenance_mode: boolean;
  debug_mode: boolean;
}

export interface BotSettings {
  max_active_bots: number;
  response_delay: number;
  activity_level: number;
  auto_learning: boolean;
  emotional_engine: boolean;
  context_memory: boolean;
}

export interface AuthSettings {
  jwt_expiry_hours: number;
  refresh_token_expiry_days: number;
  max_login_attempts: number;
  lockout_duration_minutes: number;
  two_factor_enabled: boolean;
  session_timeout_minutes: number;
}

export interface ModerationSettings {
  auto_flag_threshold: number;
  toxicity_threshold: number;
  spam_detection: boolean;
  profanity_filter: boolean;
  image_moderation: boolean;
  link_scanning: boolean;
}

export interface NotificationSettings {
  email_notifications: boolean;
  push_notifications: boolean;
  sms_notifications: boolean;
  admin_alerts: boolean;
  report_digest: 'hourly' | 'daily' | 'weekly';
  critical_alerts_email: string;
}

export interface AllSettings {
  general: GeneralSettings;
  bot: BotSettings;
  auth: AuthSettings;
  moderation: ModerationSettings;
  notifications: NotificationSettings;
  updated_at: string | null;
}

export interface UpdateSettingsRequest {
  general?: GeneralSettings;
  bot?: BotSettings;
  auth?: AuthSettings;
  moderation?: ModerationSettings;
  notifications?: NotificationSettings;
}

// API Error class
export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'APIError';
  }
}

// Generic fetch wrapper with error handling
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Add admin auth header for development
  // In production, this should come from a proper auth system
  if (typeof window !== 'undefined') {
    const adminUserId = localStorage.getItem('admin_user_id');
    if (adminUserId) {
      (headers as Record<string, string>)['X-User-ID'] = adminUserId;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch {
      errorData = null;
    }
    throw new APIError(
      errorData?.detail || `HTTP ${response.status}`,
      response.status,
      errorData
    );
  }

  return response.json();
}

// Analytics API
export const analyticsApi = {
  getOverview: (startDate?: string, endDate?: string, granularity = 'day') =>
    apiFetch<OverviewMetrics>(
      `/analytics/overview?granularity=${granularity}${startDate ? `&start_date=${startDate}` : ''}${endDate ? `&end_date=${endDate}` : ''}`
    ),

  getEngagement: (startDate?: string, endDate?: string, granularity = 'day') =>
    apiFetch<EngagementMetrics>(
      `/analytics/engagement?granularity=${granularity}${startDate ? `&start_date=${startDate}` : ''}${endDate ? `&end_date=${endDate}` : ''}`
    ),

  getBotMetrics: (startDate?: string, endDate?: string, granularity = 'day', limit = 50) =>
    apiFetch<BotMetricsResponse>(
      `/analytics/bots?granularity=${granularity}&limit=${limit}${startDate ? `&start_date=${startDate}` : ''}${endDate ? `&end_date=${endDate}` : ''}`
    ),

  getRealtime: () =>
    apiFetch<{
      active_users_now: number;
      active_bots_now: number;
      active_sessions: number;
      posts_last_hour: number;
      comments_last_hour: number;
      likes_last_hour: number;
      dms_last_hour: number;
      chats_last_hour: number;
      events_last_5min: number;
      timestamp: string;
    }>('/analytics/realtime'),

  getHeatmap: (days = 30, metric: 'posts' | 'comments' | 'likes' | 'all' = 'all') =>
    apiFetch<ActivityHeatmapResponse>(
      `/analytics/heatmap?days=${days}&metric=${metric}`
    ),

  getSentiment: (startDate?: string, endDate?: string, contentType = 'posts', granularity = 'day') =>
    apiFetch<SentimentAnalysisResponse>(
      `/analytics/sentiment?content_type=${contentType}&granularity=${granularity}${startDate ? `&start_date=${startDate}` : ''}${endDate ? `&end_date=${endDate}` : ''}`
    ),

  getUserMetrics: (startDate?: string, endDate?: string, granularity = 'day', limit = 50) =>
    apiFetch<UserMetricsResponse>(
      `/analytics/users?granularity=${granularity}&limit=${limit}${startDate ? `&start_date=${startDate}` : ''}${endDate ? `&end_date=${endDate}` : ''}`
    ),
};

// Admin API
export const adminApi = {
  getStats: () => apiFetch<DashboardStats>('/admin/stats'),

  // Bots
  listBots: (params?: { include_deleted?: boolean; include_paused?: boolean; search?: string; limit?: number; offset?: number }) => {
    const queryParams = new URLSearchParams();
    if (params?.include_deleted !== undefined) queryParams.set('include_deleted', String(params.include_deleted));
    if (params?.include_paused !== undefined) queryParams.set('include_paused', String(params.include_paused));
    if (params?.search) queryParams.set('search', params.search);
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    return apiFetch<BotListItem[]>(`/admin/bots?${queryParams.toString()}`);
  },

  getBot: (botId: string) => apiFetch<BotDetails>(`/admin/bots/${botId}`),

  updateBot: (botId: string, data: Partial<BotDetails>) =>
    apiFetch<{ status: string; bot_id: string }>(`/admin/bots/${botId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  pauseBot: (botId: string, reason?: string) =>
    apiFetch<{ status: string; bot_id: string }>(`/admin/bots/${botId}/pause`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  resumeBot: (botId: string) =>
    apiFetch<{ status: string; bot_id: string }>(`/admin/bots/${botId}/resume`, {
      method: 'POST',
    }),

  deleteBot: (botId: string, reason?: string) =>
    apiFetch<{ status: string; bot_id: string }>(`/admin/bots/${botId}`, {
      method: 'DELETE',
      body: JSON.stringify({ reason }),
    }),

  // Users
  listUsers: (params?: { include_banned?: boolean; search?: string; limit?: number; offset?: number }) => {
    const queryParams = new URLSearchParams();
    if (params?.include_banned !== undefined) queryParams.set('include_banned', String(params.include_banned));
    if (params?.search) queryParams.set('search', params.search);
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    return apiFetch<UserListItem[]>(`/admin/users?${queryParams.toString()}`);
  },

  getUser: (userId: string) => apiFetch<UserDetails>(`/admin/users/${userId}`),

  banUser: (userId: string, reason?: string) =>
    apiFetch<{ status: string; user_id: string }>(`/admin/users/${userId}/ban`, {
      method: 'PUT',
      body: JSON.stringify({ reason }),
    }),

  unbanUser: (userId: string) =>
    apiFetch<{ status: string; user_id: string }>(`/admin/users/${userId}/unban`, {
      method: 'PUT',
    }),

  // Posts
  listPosts: (params?: { include_deleted?: boolean; community_id?: string; author_id?: string; limit?: number; offset?: number }) => {
    const queryParams = new URLSearchParams();
    if (params?.include_deleted !== undefined) queryParams.set('include_deleted', String(params.include_deleted));
    if (params?.community_id) queryParams.set('community_id', params.community_id);
    if (params?.author_id) queryParams.set('author_id', params.author_id);
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    return apiFetch<PostListItem[]>(`/admin/posts?${queryParams.toString()}`);
  },

  deletePost: (postId: string, reason?: string) =>
    apiFetch<{ status: string; post_id: string }>(`/admin/posts/${postId}`, {
      method: 'DELETE',
      body: JSON.stringify({ reason }),
    }),

  // Content
  listFlaggedContent: (status?: string, limit?: number, offset?: number) => {
    const queryParams = new URLSearchParams();
    if (status) queryParams.set('status', status);
    if (limit) queryParams.set('limit', String(limit));
    if (offset) queryParams.set('offset', String(offset));
    return apiFetch<Report[]>(`/admin/flagged?${queryParams.toString()}`);
  },

  // System
  getLogs: (params?: { level?: string; source?: string; limit?: number; offset?: number }) => {
    const queryParams = new URLSearchParams();
    if (params?.level) queryParams.set('level', params.level);
    if (params?.source) queryParams.set('source', params.source);
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    return apiFetch<SystemLog[]>(`/admin/logs?${queryParams.toString()}`);
  },

  getEngineStatus: () => apiFetch<EngineStatus>('/admin/engine/status'),

  restartEngine: () =>
    apiFetch<{ status: string; message: string }>('/admin/engine/restart', {
      method: 'POST',
    }),

  // Authenticity Mode
  getAuthenticityMode: () => apiFetch<AuthenticityMode>('/admin/authenticity-mode'),

  setAuthenticityMode: (demoMode: boolean) =>
    apiFetch<AuthenticityMode>('/admin/authenticity-mode', {
      method: 'POST',
      body: JSON.stringify({ demo_mode: demoMode }),
    }),
};

// Communities API
export const communitiesApi = {
  list: () => apiFetch<Community[]>('/communities'),

  get: (communityId: string) => apiFetch<Community>(`/communities/${communityId}`),

  create: (data: { name: string; description: string; theme: string; tone?: string; topics?: string[]; initial_bot_count?: number }) =>
    apiFetch<Community>('/communities', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// Health API
export const healthApi = {
  check: () => apiFetch<HealthStatus>('/health'),

  detailed: () => apiFetch<HealthStatus>('/health/detailed'),
};

// Settings API
export const settingsApi = {
  // Get all settings
  getAll: () => apiFetch<AllSettings>('/settings'),

  // Update settings (partial update)
  update: (settings: UpdateSettingsRequest) =>
    apiFetch<AllSettings>('/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

  // Reset all settings to defaults
  reset: () =>
    apiFetch<AllSettings>('/settings/reset', {
      method: 'POST',
    }),

  // Individual section getters
  getGeneral: () => apiFetch<GeneralSettings>('/settings/general'),
  getBot: () => apiFetch<BotSettings>('/settings/bot'),
  getAuth: () => apiFetch<AuthSettings>('/settings/auth'),
  getModeration: () => apiFetch<ModerationSettings>('/settings/moderation'),
  getNotifications: () => apiFetch<NotificationSettings>('/settings/notifications'),

  // Individual section updaters
  updateGeneral: (settings: GeneralSettings) =>
    apiFetch<GeneralSettings>('/settings/general', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

  updateBot: (settings: BotSettings) =>
    apiFetch<BotSettings>('/settings/bot', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

  updateAuth: (settings: AuthSettings) =>
    apiFetch<AuthSettings>('/settings/auth', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

  updateModeration: (settings: ModerationSettings) =>
    apiFetch<ModerationSettings>('/settings/moderation', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

  updateNotifications: (settings: NotificationSettings) =>
    apiFetch<NotificationSettings>('/settings/notifications', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
};

// Platform API
export const platformApi = {
  getStats: () =>
    apiFetch<{
      total_communities: number;
      active_bots: number;
      retired_bots: number;
      llm_stats: Record<string, unknown>;
      scheduler_stats: Record<string, unknown>;
    }>('/platform/stats'),

  initialize: (numCommunities = 10) =>
    apiFetch<{
      status: string;
      communities_created: number;
      communities: Array<{ id: string; name: string; bots: number }>;
    }>(`/platform/initialize?num_communities=${numCommunities}`, {
      method: 'POST',
    }),
};

// System API
export interface SystemResources {
  cpu_percent: number;
  cpu_count: number;
  memory_used_gb: number;
  memory_total_gb: number;
  memory_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
  disk_percent: number;
  network_sent_mb_s: number;
  network_recv_mb_s: number;
}

export interface SystemServiceStatus {
  name: string;
  status: 'online' | 'offline' | 'degraded';
  metrics: { label: string; value: string }[];
}

export interface SystemStatusData {
  uptime_seconds: number;
  server_start_time: string;
  resources: SystemResources;
  services: SystemServiceStatus[];
  active_connections: number;
  python_version: string;
  pid: number;
}

export interface PerformancePoint {
  time: string;
  cpu: number;
  memory: number;
  disk_io_read: number;
  disk_io_write: number;
}

export interface PerformanceResponse {
  data_points: PerformancePoint[];
  summary: Record<string, number>;
}

export interface SystemLogEntry {
  id: number;
  timestamp: string;
  level: string;
  message: string;
  details: string;
  source: string;
}

export interface SystemLogsResponse {
  logs: SystemLogEntry[];
  total: number;
}

export const systemApi = {
  getStatus: () => apiFetch<SystemStatusData>('/system/status'),

  getPerformance: (points = 30) =>
    apiFetch<PerformanceResponse>(`/system/performance?points=${points}`),

  getLogs: (params?: { level?: string; search?: string; limit?: number; offset?: number }) => {
    const queryParams = new URLSearchParams();
    if (params?.level) queryParams.set('level', params.level);
    if (params?.search) queryParams.set('search', params.search);
    if (params?.limit) queryParams.set('limit', String(params.limit));
    if (params?.offset) queryParams.set('offset', String(params.offset));
    return apiFetch<SystemLogsResponse>(`/system/logs?${queryParams.toString()}`);
  },
};

// Moderation API (for reports page)
export interface ModerationReport {
  id: string;
  reporter_id: string;
  target_type: string;
  target_id: string;
  report_type: string;
  reason: string;
  status: string;
  created_at: string;
  reviewed_at: string | null;
  reviewer_id: string | null;
  action_taken: string | null;
  notes: string | null;
  auto_flagged: boolean;
}

export interface ModerationReportStats {
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  total_reports: number;
  auto_flagged_count: number;
  avg_resolution_hours: number;
}

export const moderationApi = {
  listReports: (status?: string, limit = 50) => {
    const queryParams = new URLSearchParams();
    if (status) queryParams.set('status', status);
    queryParams.set('limit', String(limit));
    return apiFetch<ModerationReport[]>(`/moderation/reports?${queryParams.toString()}`);
  },

  getReportStats: () =>
    apiFetch<ModerationReportStats>('/moderation/reports/stats'),

  getReport: (reportId: string) =>
    apiFetch<ModerationReport>(`/moderation/reports/${reportId}`),

  reviewReport: (reportId: string, reviewerId: string, action: string, notes?: string) =>
    apiFetch<ModerationReport>(`/moderation/reports/${reportId}/review?reviewer_id=${reviewerId}`, {
      method: 'POST',
      body: JSON.stringify({ action, notes }),
    }),

  dismissReport: (reportId: string, reviewerId: string, notes?: string) =>
    apiFetch<ModerationReport>(`/moderation/reports/${reportId}/dismiss?reviewer_id=${reviewerId}&notes=${notes || ''}`, {
      method: 'POST',
    }),
};

// Utility functions
export function formatApiDate(date: Date): string {
  return date.toISOString().split('T')[0];
}

export function getDateRange(range: string): { startDate: string; endDate: string } {
  const endDate = new Date();
  const startDate = new Date();

  switch (range) {
    case '24h':
    case '1d':
      startDate.setDate(startDate.getDate() - 1);
      break;
    case '7d':
      startDate.setDate(startDate.getDate() - 7);
      break;
    case '30d':
      startDate.setDate(startDate.getDate() - 30);
      break;
    case '90d':
      startDate.setDate(startDate.getDate() - 90);
      break;
    default:
      startDate.setDate(startDate.getDate() - 7);
  }

  return {
    startDate: formatApiDate(startDate),
    endDate: formatApiDate(endDate),
  };
}
