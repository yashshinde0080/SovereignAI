'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ModelTable } from '@/components/models/ModelTable';
import { DownloadModal } from '@/components/models/DownloadModal';
import { CloudModelList } from '@/components/models/CloudModelList';
import { CloudProvidersSettings } from '@/components/settings/CloudProvidersSettings';
import { OnlineServices } from '@/components/models/OnlineServices';
import { useModels } from '@/hooks/useModels';
import { useStore } from '@/store';
import { Plus, RefreshCw, HardDrive, Cloud } from 'lucide-react';

export default function ModelsPage() {
  const { models, loading, loadingId, refresh, loadModel, unloadModel, deleteModel, downloadModel, downloadStatus } = useModels();
  const { currentModel } = useStore();
  const [downloadModalOpen, setDownloadModalOpen] = useState(false);
  // Provider add/toggle/delete refreshes the cloud model list (live provider fetch).
  const [providerVersion, setProviderVersion] = useState(0);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Models</h1>
        <p className="text-muted-foreground">
          Manage local models (offline) and cloud API models (online)
        </p>
      </div>

      <Tabs defaultValue="offline">
        <TabsList>
          <TabsTrigger value="offline">
            <HardDrive className="h-4 w-4" />
            Offline
          </TabsTrigger>
          <TabsTrigger value="online">
            <Cloud className="h-4 w-4" />
            Online
          </TabsTrigger>
        </TabsList>

        {/* Offline: local models on disk, run via FullRAM / LayerStream */}
        <TabsContent value="offline" className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>Installed Models</CardTitle>
                <CardDescription>
                  {models.length} model{models.length !== 1 ? 's' : ''} installed locally
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={refresh} disabled={loading}>
                  <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
                <Button onClick={() => setDownloadModalOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Download Model
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <ModelTable
                models={models}
                currentModel={currentModel}
                onLoad={loadModel}
                onUnload={unloadModel}
                onDelete={deleteModel}
                loading={loading}
                loadingId={loadingId}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Online: cloud API models — no local engine, no RAM/VRAM needed */}
        <TabsContent value="online" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Online Models</CardTitle>
              <CardDescription>
                Served by connected providers over the network — no FullRAM or
                LayerStream engine, no local download, no RAM/VRAM usage. Load one,
                then hit Chat to use it.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CloudModelList refreshKey={providerVersion} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Providers</CardTitle>
              <CardDescription>
                API keys are encrypted on your machine and never leave the backend
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CloudProvidersSettings onChanged={() => setProviderVersion((v) => v + 1)} />
            </CardContent>
          </Card>

          <OnlineServices />
        </TabsContent>
      </Tabs>

      <DownloadModal
        open={downloadModalOpen}
        onClose={() => setDownloadModalOpen(false)}
        onDownload={downloadModel}
        downloadStatus={downloadStatus}
      />
    </div>
  );
}