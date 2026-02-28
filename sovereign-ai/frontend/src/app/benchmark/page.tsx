'use client'

import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useStore } from '@/store/useStore'
import { CheckCircle, Play } from 'lucide-react'

interface BenchmarkResult {
  model: string;
  mode: string;
  tokens_per_sec: number;
  first_token_latency_ms: number;
  peak_ram_gb: number;
}

export default function BenchmarkPage() {
  const { currentModel } = useStore()
  const [results, setResults] = useState<BenchmarkResult[]>([])
  const [loading, setLoading] = useState(false)

  const runBenchmark = async () => {
    setLoading(true)
    try {
      const res = await fetch('http://127.0.0.1:8000/v1/benchmark', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: currentModel })
      })
      const data = await res.json()
      setResults(prev => [data, ...prev])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Performance Benchmarks</h2>
          <p className="text-sm text-muted-foreground">Compare tokens-per-second, memory usage, and execution modes.</p>
        </div>
        <Button
          onClick={runBenchmark}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700"
        >
          {loading ? <span className="animate-spin mr-2">⟳</span> : <Play className="mr-2 h-4 w-4" />}
          Run on {currentModel}
        </Button>
      </div>

      <Card className="border-slate-800 bg-slate-900 overflow-hidden">
        <Table>
          <TableHeader className="bg-slate-800/50">
            <TableRow className="border-slate-800">
              <TableHead className="text-slate-300">Model</TableHead>
              <TableHead className="text-slate-300">Execution Mode</TableHead>
              <TableHead className="text-right text-slate-300">Tokens/sec</TableHead>
              <TableHead className="text-right text-slate-300">TTFT (ms)</TableHead>
              <TableHead className="text-right text-slate-300">Peak RAM (GB)</TableHead>
              <TableHead className="text-center text-slate-300">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {results.length === 0 ? (
              <TableRow className="border-slate-800">
                <TableCell colSpan={6} className="h-24 text-center text-slate-500 font-mono">
                  No benchmarks run yet. Execute a test.
                </TableCell>
              </TableRow>
            ) : (
              results.map((res, i) => (
                <TableRow key={i} className="border-slate-800 transition-colors hover:bg-slate-800/50">
                  <TableCell className="font-mono text-blue-400 font-medium">{res.model}</TableCell>
                  <TableCell>
                    <span className="px-2 py-1 rounded bg-slate-800 text-xs font-mono border border-slate-700">
                      {res.mode.toUpperCase()}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono">{res.tokens_per_sec.toFixed(1)}</TableCell>
                  <TableCell className="text-right font-mono">{res.first_token_latency_ms}</TableCell>
                  <TableCell className="text-right font-mono text-yellow-400">{res.peak_ram_gb.toFixed(1)}</TableCell>
                  <TableCell className="text-center">
                    <CheckCircle className="h-4 w-4 text-green-500 mx-auto" />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
