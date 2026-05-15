import { useCallback, useEffect, useRef, useState } from 'react'
import { AgentUpdate } from '../types'

interface UseWebSocketOptions {
  onMessage: (msg: AgentUpdate) => void
  onComplete: (data: Record<string, unknown>) => void
  onError: (error: string) => void
}

export function useWebSocket({ onMessage, onComplete, onError }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)

  const connect = useCallback(
    (query: string, userId = 'anonymous') => {
      const sessionId = crypto.randomUUID()
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/travel/${sessionId}`

      if (wsRef.current) {
        wsRef.current.close()
      }

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        ws.send(JSON.stringify({ query, user_id: userId }))
      }

      ws.onmessage = (event) => {
        const msg: AgentUpdate = JSON.parse(event.data)
        if (msg.type === 'complete') {
          onComplete(msg.data || {})
        } else if (msg.type === 'error') {
          onError(msg.message)
        } else {
          onMessage(msg)
        }
      }

      ws.onerror = () => {
        onError('WebSocket connection failed')
        setConnected(false)
      }

      ws.onclose = () => {
        setConnected(false)
      }
    },
    [onMessage, onComplete, onError],
  )

  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  return { connect, connected }
}
