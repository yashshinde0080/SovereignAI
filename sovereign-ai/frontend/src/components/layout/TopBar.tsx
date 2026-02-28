'use client'

import { useStore } from '@/store/useStore'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'

export function TopBar() {
  const { currentModel, currentMode, ramUsage, tps, status } = useStore()

  return (
    <div className="flex items-center justify-between px-6 py-3 border-b bg-slate-900 text-slate-200">
      <div className="flex items-center space-x-4">
        <h1 className="font-bold text-lg tracking-tight">SovereignAI Edge</h1>
        <Separator orientation="vertical" className="h-6" />
        <Badge variant="outline" className="text-slate-300 border-slate-700">Model: {currentModel}</Badge>
        <Badge variant={currentMode === 'fullram' ? 'default' : 'secondary'} className={currentMode === 'fullram' ? 'bg-blue-600 hover:bg-blue-700' : ''}>Mode: {currentMode.toUpperCase()}</Badge>
      </div>

      <div className="flex items-center space-x-4 text-sm font-mono">
        <span className="flex items-center"><span className="w-2 h-2 rounded-full mr-2 bg-green-500"></span>{status.toUpperCase()}</span>
        <Separator orientation="vertical" className="h-4" />
        <span>RAM: {ramUsage.toFixed(1)}GB</span>
        <Separator orientation="vertical" className="h-4" />
        <span>TPS: {tps.toFixed(1)}</span>
      </div>
    </div>
  )
}
