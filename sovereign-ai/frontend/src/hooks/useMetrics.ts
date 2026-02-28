'use client'

import { useEffect } from 'react'
import { useStore } from '@/store/useStore'

export function useMetrics() {
  const updateMetrics = useStore((state) => state.updateMetrics)

  useEffect(() => {
    // Only connect in browser environment
    if (typeof window === 'undefined') return

    const ws = new WebSocket('ws://127.0.0.1:8000/ws/metrics')

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        updateMetrics({
          ramUsage: data.ram_usage,
          diskIO: data.disk_io,
          tps: data.tokens_per_sec,
          kvCache: data.kv_cache,
          currentMode: data.mode,
          currentModel: data.model,
          status: data.status,
        })
      } catch (e) {
        console.error('Failed to parse websocket metrics', e)
      }
    }

    return () => {
      ws.close()
    }
  }, [updateMetrics])
}
