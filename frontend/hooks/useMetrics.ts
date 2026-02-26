'use client';

import { useEffect, useState, useRef } from 'react';
import { useStore } from '@/store';
import { metricsWs } from '@/lib/websocket';

interface MetricPoint {
  time: string;
  cpu: number;
  ram: number;
}

export function useMetrics() {
  const { metrics, setMetrics } = useStore();
  const [history, setHistory] = useState<MetricPoint[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    metricsWs.connect();

    const unsubscribe = metricsWs.subscribe((data) => {
      setMetrics(data);
      setConnected(true);

      const now = new Date().toLocaleTimeString();
      setHistory((prev) => {
        const newHistory = [
          ...prev,
          { time: now, cpu: data.cpu_percent, ram: data.ram_percent },
        ];
        // Keep last 60 points
        return newHistory.slice(-60);
      });
    });

    // Check connection status
    const interval = setInterval(() => {
      setConnected(metricsWs.isConnected());
    }, 1000);

    return () => {
      unsubscribe();
      clearInterval(interval);
    };
  }, [setMetrics]);

  return { metrics, history, connected };
}