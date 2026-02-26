'use client';

import { useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/use-toast';
import { Plugin } from '@/types';

export function usePlugins() {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listPlugins();
      setPlugins(res || []);
    } catch (error: any) {
      toast({
        title: 'Failed to load plugins',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const enablePlugin = useCallback(async (pluginId: string) => {
    try {
      await api.enablePlugin(pluginId);
      await refresh();
      toast({
        title: 'Plugin enabled',
        description: `${pluginId} is now active`,
      });
    } catch (error: any) {
      toast({
        title: 'Failed to enable plugin',
        description: error.message,
        variant: 'destructive',
      });
    }
  }, [refresh, toast]);

  const disablePlugin = useCallback(async (pluginId: string) => {
    try {
      await api.disablePlugin(pluginId);
      await refresh();
      toast({
        title: 'Plugin disabled',
        description: `${pluginId} is now inactive`,
      });
    } catch (error: any) {
      toast({
        title: 'Failed to disable plugin',
        description: error.message,
        variant: 'destructive',
      });
    }
  }, [refresh, toast]);

  return {
    plugins,
    loading,
    refresh,
    enablePlugin,
    disablePlugin,
  };
}