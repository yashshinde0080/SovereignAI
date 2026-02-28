import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TerminalSquare } from 'lucide-react'

export default function LogsPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">System Logs</h2>
          <p className="text-sm text-muted-foreground">View execution logs and inference diagnostics.</p>
        </div>
      </div>

      <Card className="border-slate-800 bg-slate-900 overflow-hidden h-[600px] flex flex-col">
        <CardHeader className="bg-slate-950/50 py-3 border-b border-slate-800">
          <CardTitle className="text-sm font-mono flex items-center text-slate-300">
            <TerminalSquare className="mr-2 h-4 w-4" />
            tail -f /var/log/sovereign-ai/engine.log
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 p-0 bg-black font-mono text-xs overflow-y-auto">
          <div className="p-4 space-y-1">
            <div className="text-slate-400">[INFO] Application startup complete.</div>
            <div className="text-blue-400">[INFO] Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)</div>
            <div className="text-slate-400">[INFO] 127.0.0.1:38904 - &quot;GET /v1/models HTTP/1.1&quot; 200 OK</div>
            <div className="text-slate-400">[INFO] sovereign-websocket: Client connected to metrics</div>
            <div className="text-yellow-400">[WARN] Engine requested LAYERSTREAM mode for model llama3:8b</div>
            <div className="text-green-400">[INFO] Memory Scheduler initialized. Max RAM constraint: 12.4 GB</div>
            <div className="text-slate-400">[INFO] Preloading layer buffers via mmap...</div>
            <div className="text-slate-400">[INFO] System ready for inference.</div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
