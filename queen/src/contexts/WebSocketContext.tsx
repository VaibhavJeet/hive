'use client'

import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { getWebSocketManager, ConnectionStatus, EventHandlers } from '@/lib/websocket'
import { onAuthChange } from '@/lib/auth'

interface WebSocketContextValue {
  status: ConnectionStatus
  isConnected: boolean
  connect: () => Promise<void>
  disconnect: () => void
  subscribe: <T extends keyof EventHandlers>(
    event: T,
    callback: EventHandlers[T]
  ) => () => void
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [isReady, setIsReady] = useState(false)

  const wsManager = getWebSocketManager()

  // Connect on mount
  useEffect(() => {
    const unsubscribeStatus = wsManager.onStatusChange(setStatus)

    // Identity comes from the session. `connect()` resolves without opening a socket
    // when signed out, so public civilization pages still render for anonymous visitors.
    const openSocket = () => {
      wsManager
        .connect()
        .catch(error => {
          console.error('WebSocket connection failed:', error)
        })
        .finally(() => setIsReady(true))
    }

    openSocket()

    // Re-evaluate on login/logout: open a socket once a session exists, drop it on logout.
    const unsubscribeAuth = onAuthChange(() => {
      wsManager.disconnect()
      openSocket()
    })

    return () => {
      unsubscribeStatus()
      unsubscribeAuth()
      // Don't disconnect on cleanup - keep connection alive across route changes
    }
  }, [wsManager])

  const connect = useCallback(async () => {
    await wsManager.connect()
  }, [wsManager])

  const disconnect = useCallback(() => {
    wsManager.disconnect()
  }, [wsManager])

  const subscribe = useCallback(<T extends keyof EventHandlers>(
    event: T,
    callback: EventHandlers[T]
  ): (() => void) => {
    return wsManager.on(event, callback)
  }, [wsManager])

  const value: WebSocketContextValue = {
    status,
    isConnected: status === 'connected',
    connect,
    disconnect,
    subscribe,
  }

  // Show loading indicator until ready
  if (!isReady) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin" />
          <span className="text-[#666666] text-xs font-mono uppercase tracking-wider">
            Connecting...
          </span>
        </div>
      </div>
    )
  }

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocket(): WebSocketContextValue {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}

// Convenience hook for subscribing to specific events
export function useWebSocketEvent<T extends keyof EventHandlers>(
  event: T,
  callback: EventHandlers[T],
  deps: React.DependencyList = []
): void {
  const { subscribe } = useWebSocket()

  useEffect(() => {
    const unsubscribe = subscribe(event, callback)
    return unsubscribe
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event, subscribe, ...deps])
}

// Hook for connection status
export function useConnectionStatus(): {
  status: ConnectionStatus
  isConnected: boolean
  statusColor: string
  statusText: string
} {
  const { status, isConnected } = useWebSocket()

  const statusColor = {
    connected: '#44ff88',
    connecting: '#ffaa00',
    reconnecting: '#ffaa00',
    disconnected: '#ff4444',
  }[status]

  const statusText = {
    connected: 'Live',
    connecting: 'Connecting',
    reconnecting: 'Reconnecting',
    disconnected: 'Offline',
  }[status]

  return { status, isConnected, statusColor, statusText }
}
