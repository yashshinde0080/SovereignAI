import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export default async function SystemPage() {
  const res = await fetch('http://127.0.0.1:8000/v1/system', { cache: 'no-store' })
  const profile = await res.json()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">System Metrics</h2>
        <p className="text-sm text-muted-foreground">Hardware profile and diagnostic capabilities.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader>
            <CardTitle className="text-lg flex justify-between">
              Processor Details
              <Badge className="bg-slate-800 text-blue-400">AVX2: {profile.avx2 ? 'Yes' : 'No'}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Physical Cores:</span>
              <span className="font-mono">{profile.cpu_cores}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Logical Threads:</span>
              <span className="font-mono">{profile.logical_cores}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">GPU Acceleration:</span>
              <span className="font-mono">{profile.gpu}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900">
          <CardHeader>
            <CardTitle className="text-lg">Memory & Storage</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Total System RAM:</span>
              <span className="font-mono">{profile.ram_total_gb} GB</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Available RAM:</span>
              <span className="font-mono">{profile.ram_available_gb} GB</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Disk Read Speed:</span>
              <span className="font-mono text-green-400">{profile.disk_speed_mb_s} MB/s</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-slate-900 border-l-4 border-l-blue-500">
        <CardContent className="pt-6">
          <p className="text-sm text-slate-300">
            Based on this profile, the recommended execution mode for models up to 7B is <strong className="text-white">FULLRAM</strong>.
            Larger models will automatically fall back to <strong className="text-white">LAYERSTREAM</strong> scheduling to avoid swapping.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
