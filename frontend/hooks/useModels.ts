'use client';

import { useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { useStore } from '@/store';
import { useToast } from '@/components/ui/use-toast';
import { Model } from '@/types';

export function useModels() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloadStatus, setDownloadStatus] = useState<any>(null);
  const { setSystemStatus } = useStore();
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

  const loadModel = useCallback(async (model: string) => {
    setLoading(true);
    try {
      const result = await api.loadModel(model);
      const status = await api.getSystemStatus();
      setSystemStatus(status as any);
      toast({
        title: 'Model loaded',
        description: `${model} is now ready`,
      });
    } catch (error: any) {
      toast({
        title: 'Failed to load model',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [setSystemStatus, toast]);

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
          const status = await api.getPullStatus(model);
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

  return {
    models,
    loading,
    refresh,
    loadModel,
    deleteModel,
    downloadModel,
    downloadStatus,
  };
}