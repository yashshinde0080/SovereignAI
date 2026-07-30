'use client';

import { useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { useStore } from '@/store';
import { useToast } from '@/components/ui/use-toast';
import { Model } from '@/types';

export function useModels() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [downloadStatus, setDownloadStatus] = useState<any>(null);
  const { setSystemStatus, setCurrentModel, setTaskType, setIsGenerative, setExecutionMode } = useStore();
  const { toast } = useToast();

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listModels();
      setModels(res.models || []);
    } catch (error: any) {
      toast({
        title: 'Failed to load models',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  function notify(title: string, body: string) {
    if (typeof window !== 'undefined' && (window as any).electronAPI?.showNotification) {
      (window as any).electronAPI.showNotification({ title, body });
    }
  }

  const loadModel = useCallback(async (model: string) => {
    setLoading(true);
    setLoadingId(model);
    try {
      const result = await api.loadModel(model);
      const status = await api.getSystemStatus();
      setSystemStatus(status as any);
      
      const current = await api.getCurrentModel() as any;
      if (current.loaded) {
        setCurrentModel(current.model);
        setTaskType(current.task_type);
        setExecutionMode(current.mode);
        setIsGenerative(current.is_generative);
      }
      
      toast({
        title: 'Model loaded',
        description: `${model} is ready for ${current.task_type?.replace(/_/g, ' ')}`,
      });
      notify('Model loaded', `${model} is ready for inference.`);
    } catch (error: any) {
      toast({
        title: 'Failed to load model',
        description: error.message,
        variant: 'destructive',
      });
      notify('Model load failed', error.message);
    } finally {
      setLoading(false);
      setLoadingId(null);
    }
  }, [setSystemStatus, setCurrentModel, setTaskType, setIsGenerative, setExecutionMode, toast]);

  const unloadModel = useCallback(async () => {
    const activeId = useStore.getState().currentModel;
    setLoading(true);
    if (activeId) setLoadingId(activeId);
    try {
      await api.unloadModel();
      const status = await api.getSystemStatus();
      setSystemStatus(status as any);
      setCurrentModel('');
      setTaskType('');
      setIsGenerative(false);
      
      toast({
        title: 'Model unloaded',
        description: 'System is ready',
      });
      if (activeId) notify('Model unloaded', `${activeId} has been unloaded.`);
    } catch (error: any) {
      toast({
        title: 'Failed to unload model',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
      setLoadingId(null);
    }
  }, [setSystemStatus, toast, setCurrentModel, setTaskType, setIsGenerative]);

  const deleteModel = useCallback(async (model: string) => {
    try {
      await api.deleteModel(model);
      await refresh();
      toast({
        title: 'Model deleted',
        description: `${model} has been removed`,
      });
    } catch (error: any) {
      toast({
        title: 'Failed to delete model',
        description: error.message,
        variant: 'destructive',
      });
    }
  }, [refresh, toast]);

  const downloadModel = useCallback(async (model: string, quant: string) => {
    try {
      await api.pullModel(model, quant);
      
      // Poll for status
      const pollStatus = async () => {
        try {
          const status = await api.getPullStatus(model) as any;
          setDownloadStatus(status);
          
          if (status.status === 'downloading' || status.status === 'verifying' || status.status === 'encrypting') {
            setTimeout(pollStatus, 1000);
          } else if (status.status === 'complete') {
            await refresh();
            toast({
              title: 'Download complete',
              description: `${model} is ready to use`,
            });
            setDownloadStatus(null);
          } else if (status.status === 'error') {
            toast({
              title: 'Download failed',
              description: status.error || 'Unknown error',
              variant: 'destructive',
            });
            setDownloadStatus(null);
          }
        } catch (error) {
          console.error('Poll error:', error);
        }
      };
      
      pollStatus();
    } catch (error: any) {
      toast({
        title: 'Failed to start download',
        description: error.message,
        variant: 'destructive',
      });
    }
  }, [refresh, toast]);

  const switchMode = useCallback(async (mode: string) => {
    setLoading(true);
    try {
      await api.switchMode(mode);
      const current = await api.getCurrentModel() as any;
      if (current.loaded) {
        setExecutionMode(current.mode);
      }
      toast({
        title: 'Mode switched',
        description: `Now using ${mode} mode`,
      });
    } catch (error: any) {
      toast({
        title: 'Failed to switch mode',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [setExecutionMode, toast]);

  return {
    models,
    loading,
    loadingId,
    refresh,
    loadModel,
    unloadModel,
    deleteModel,
    downloadModel,
    downloadStatus,
    switchMode,
  };
}
