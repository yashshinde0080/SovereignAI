'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useStore } from '@/store';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/use-toast';
import { Save, FolderOpen, Trash2, Clock, Cpu } from 'lucide-react';

interface WorkspaceSnapshot {
  id: string;
  model: string | null;
  mode: string | null;
  timestamp: number;
  created: string;
}

export default function WorkspacePage() {
  const { currentModel, executionMode, setCurrentModel, setExecutionMode } = useStore();
  const { toast } = useToast();
  const [snapshots, setSnapshots] = useState<WorkspaceSnapshot[]>([]);
  const [saving, setSaving] = useState(false);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const loadSnapshots = async () => {
    try {
      const res = await api.listWorkspaces();
      setSnapshots(res.snapshots || []);
    } catch (e: any) {
      toast({ title: 'Failed to load snapshots', description: e.message, variant: 'destructive' });
    }
  };

  useEffect(() => { loadSnapshots(); }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.saveWorkspace();
      await loadSnapshots();
      toast({ title: 'Snapshot saved', description: 'Current workspace saved.' });
    } catch (e: any) {
      toast({ title: 'Failed to save snapshot', description: e.message, variant: 'destructive' });
    }
    setSaving(false);
  };

  const handleLoad = async (id: string) => {
    setLoadingId(id);
    try {
      const snap: any = await api.loadWorkspace(id);
      if (snap.model) {
        await api.loadModel(snap.model, snap.mode || 'auto');
        setCurrentModel(snap.model);
        if (snap.mode) setExecutionMode(snap.mode);
        toast({ title: 'Model loaded', description: `${snap.model} restored from snapshot.` });
      }
      await loadSnapshots();
    } catch (e: any) {
      toast({ title: 'Failed to load snapshot', description: e.message, variant: 'destructive' });
    }
    setLoadingId(null);
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteWorkspace(id);
      await loadSnapshots();
    } catch (e: any) {
      toast({ title: 'Failed to delete snapshot', description: e.message, variant: 'destructive' });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Workspace Snapshots</h1>
          <p className="text-muted-foreground">Save and restore your work sessions</p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          <Save className="h-4 w-4 mr-2" />
          {saving ? 'Saving...' : 'Save Snapshot'}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Current Session</CardTitle>
          <CardDescription>Active model and mode state</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1 text-muted-foreground">
              <Cpu className="h-3 w-3" />
              Model: {currentModel || 'none'}
            </span>
            <span className="flex items-center gap-1 text-muted-foreground">
              <FolderOpen className="h-3 w-3" />
              Mode: {executionMode || 'auto'}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Saved Snapshots</CardTitle>
          <CardDescription>{snapshots.length} snapshot(s)</CardDescription>
        </CardHeader>
        <CardContent>
          {snapshots.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No snapshots saved yet</p>
              <p className="text-sm">Save your current workspace to restore it later</p>
            </div>
          ) : (
            <div className="space-y-2">
              {snapshots.map((snap: WorkspaceSnapshot) => (
                <div key={snap.id} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                  <div>
                    <p className="text-sm font-medium">{snap.model || 'no model'}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(snap.timestamp * 1000).toLocaleString()} &middot; {snap.mode || 'auto'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => handleLoad(snap.id)} disabled={loadingId === snap.id}>
                      {loadingId === snap.id ? 'Loading...' : 'Load'}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(snap.id)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
