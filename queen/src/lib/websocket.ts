/**
 * WebSocket manager for the queen portal.
 *
 * `contexts/WebSocketContext.tsx` has always imported this module, but it did not exist —
 * so `npm run build` failed at the root layout (see HIVE-131). This is the missing
 * implementation, written against the backend contract in `mind/api/main.py`.
 *
 * Identity comes from the session (HIVE-002), never from a hardcoded UUID.
 * The `auth` frame is the backend's current scheme; HIVE-017 replaces it with a token
 * handshake, at which point `connect()` should send the access token instead of the id.
 */

import { getAccessToken, getSessionUser } from './auth'

export type ConnectionStatus =
  | 'connected'
  | 'connecting'
  | 'reconnecting'
  | 'disconnected'

/**
 * Events the backend actually emits. Names verified against the `_broadcast_event`
 * call sites in `mind/engine/loops/` and `mind/civilization/`.
 */
export interface EventHandlers {
  new_post: (data: Record<string, unknown>) => void
  post_liked: (data: Record<string, unknown>) => void
  new_comment: (data: Record<string, unknown>) => void
  new_chat_message: (data: Record<string, unknown>) => void
  new_dm: (data: Record<string, unknown>) => void
  typing_start: (data: Record<string, unknown>) => void
  typing_stop: (data: Record<string, unknown>) => void
  bot_thought: (data: Record<string, unknown>) => void
  bot_evolved: (data: Record<string, unknown>) => void
  bot_self_improved: (data: Record<string, unknown>) => void
  bot_noticed: (data: Record<string, unknown>) => void
  emotional_contagion: (data: Record<string, unknown>) => void
  notification: (data: Record<string, unknown>) => void
  world_map_birth: (data: Record<string, unknown>) => void
  world_map_death: (data: Record<string, unknown>) => void
  world_map_migration: (data: Record<string, unknown>) => void
  world_map_community_created: (data: Record<string, unknown>) => void
  world_map_community_revived: (data: Record<string, unknown>) => void
  world_map_era_transition: (data: Record<string, unknown>) => void
}

type EventName = keyof EventHandlers

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(
    /^http/,
    'ws'
  )

const HEARTBEAT_INTERVAL_MS = 30_000
const MAX_RECONNECT_DELAY_MS = 30_000
const BASE_RECONNECT_DELAY_MS = 1_000

export class WebSocketManager {
  private socket: WebSocket | null = null
  private status: ConnectionStatus = 'disconnected'
  private statusListeners = new Set<(status: ConnectionStatus) => void>()
  private handlers = new Map<EventName, Set<(data: never) => void>>()

  private clientId: string | null = null
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  /** Set when the caller asked to disconnect, so we do not fight them by reconnecting. */
  private intentionallyClosed = false

  // --------------------------------------------------------------------------
  // STATUS
  // --------------------------------------------------------------------------

  getStatus(): ConnectionStatus {
    return this.status
  }

  onStatusChange(listener: (status: ConnectionStatus) => void): () => void {
    this.statusListeners.add(listener)
    listener(this.status)
    return () => this.statusListeners.delete(listener)
  }

  private setStatus(status: ConnectionStatus): void {
    if (this.status === status) return
    this.status = status
    this.statusListeners.forEach((l) => {
      try {
        l(status)
      } catch {
        // A status listener must not break the socket.
      }
    })
  }

  // --------------------------------------------------------------------------
  // EVENTS
  // --------------------------------------------------------------------------

  on<T extends EventName>(event: T, handler: EventHandlers[T]): () => void {
    let set = this.handlers.get(event)
    if (!set) {
      set = new Set()
      this.handlers.set(event, set)
    }
    set.add(handler as (data: never) => void)
    return () => {
      set!.delete(handler as (data: never) => void)
    }
  }

  private emit(event: string, data: unknown): void {
    const set = this.handlers.get(event as EventName)
    if (!set) return
    set.forEach((handler) => {
      try {
        ;(handler as (data: unknown) => void)(data)
      } catch (error) {
        console.error(`WebSocket handler for "${event}" threw:`, error)
      }
    })
  }

  // --------------------------------------------------------------------------
  // CONNECTION
  // --------------------------------------------------------------------------

  /**
   * Open the socket for the current session.
   *
   * @param clientId Optional explicit client id. Defaults to the signed-in user's id.
   *                 Resolves (rather than rejects) when unauthenticated, so an anonymous
   *                 visitor to a public civilization page still renders.
   */
  async connect(clientId?: string): Promise<void> {
    if (typeof window === 'undefined') return

    const resolvedId = clientId ?? getSessionUser()?.id ?? null
    if (!resolvedId || !getAccessToken()) {
      this.setStatus('disconnected')
      return
    }

    this.clientId = resolvedId
    this.intentionallyClosed = false

    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING)
    ) {
      return
    }

    this.setStatus(this.reconnectAttempts > 0 ? 'reconnecting' : 'connecting')

    await new Promise<void>((resolve) => {
      let settled = false
      const settle = () => {
        if (!settled) {
          settled = true
          resolve()
        }
      }

      try {
        const socket = new WebSocket(`${WS_BASE_URL}/ws/${resolvedId}`)
        this.socket = socket

        socket.onopen = () => {
          this.reconnectAttempts = 0
          this.setStatus('connected')
          // Identify this connection so the backend routes notifications to it.
          // HIVE-017: replace with a token frame once the server verifies one.
          this.send({ type: 'auth', user_id: resolvedId })
          this.startHeartbeat()
          settle()
        }

        socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data)
            if (message?.type && message.type !== 'pong') {
              this.emit(message.type, message.data ?? message)
            }
          } catch {
            // Ignore frames that are not JSON.
          }
        }

        socket.onerror = () => {
          // `onclose` always follows; reconnect logic lives there.
          settle()
        }

        socket.onclose = () => {
          this.stopHeartbeat()
          this.socket = null
          if (this.intentionallyClosed) {
            this.setStatus('disconnected')
          } else {
            this.scheduleReconnect()
          }
          settle()
        }
      } catch {
        this.setStatus('disconnected')
        this.scheduleReconnect()
        settle()
      }
    })
  }

  disconnect(): void {
    this.intentionallyClosed = true
    this.clearReconnect()
    this.stopHeartbeat()
    this.socket?.close()
    this.socket = null
    this.setStatus('disconnected')
  }

  send(payload: Record<string, unknown>): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload))
    }
  }

  // --------------------------------------------------------------------------
  // RECONNECT / HEARTBEAT
  // --------------------------------------------------------------------------

  private scheduleReconnect(): void {
    if (this.intentionallyClosed || this.reconnectTimer) return
    if (!getAccessToken()) {
      // Session ended — reconnecting would just 401 in a loop.
      this.setStatus('disconnected')
      return
    }

    this.setStatus('reconnecting')
    const delay = Math.min(
      BASE_RECONNECT_DELAY_MS * 2 ** this.reconnectAttempts,
      MAX_RECONNECT_DELAY_MS
    )
    this.reconnectAttempts += 1

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      void this.connect(this.clientId ?? undefined)
    }, delay)
  }

  private clearReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.reconnectAttempts = 0
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'ping' })
    }, HEARTBEAT_INTERVAL_MS)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }
}

let manager: WebSocketManager | null = null

export function getWebSocketManager(): WebSocketManager {
  if (!manager) manager = new WebSocketManager()
  return manager
}
