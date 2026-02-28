import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Download, Play, Trash } from 'lucide-react'

export default async function ModelsPage() {
  const modelsRes = await fetch('http://127.0.0.1:8000/v1/models', { cache: 'no-store' })
  const modelsData = await modelsRes.json()

  const models = Object.keys(modelsData).map(key => ({
    name: key,
    ...modelsData[key]
  }))

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Model Registry</h2>
        <p className="text-sm text-muted-foreground">Manage and download LLMs for offline execution.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {models.map(model => (
          <Card key={model.name} className="border-slate-800 bg-slate-900">
            <CardHeader className="pb-3">
              <div className="flex justify-between items-start">
                <CardTitle className="text-lg">{model.name}</CardTitle>
                {model.downloaded ? (
                  <Badge className="bg-green-600/20 text-green-400 hover:bg-green-600/30">Ready</Badge>
                ) : (
                  <Badge variant="secondary" className="bg-slate-800 text-slate-400">Not Installed</Badge>
                )}
              </div>
              <CardDescription className="text-xs">{model.id} • {model.quant} • {model.size_gb} GB</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex space-x-2 text-xs text-slate-400 mb-4 font-mono">
                {model.modes.map((mode: string) => (
                  <Badge key={mode} variant="outline" className="border-slate-700 bg-slate-950/50">{mode.toUpperCase()}</Badge>
                ))}
              </div>
              <div className="flex space-x-2 w-full mt-4">
                {model.downloaded ? (
                  <>
                    <Button variant="default" className="w-full bg-blue-600 hover:bg-blue-700 text-white">
                      <Play className="mr-2 h-4 w-4" /> Load
                    </Button>
                    <Button variant="destructive" size="icon" className="shrink-0 bg-red-900/40 hover:bg-red-900/80 text-red-400">
                      <Trash className="h-4 w-4" />
                    </Button>
                  </>
                ) : (
                  <Button variant="secondary" className="w-full bg-slate-800 hover:bg-slate-700 text-slate-200">
                    <Download className="mr-2 h-4 w-4" /> Download
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
