"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Play, Cloud, RefreshCw, Settings, MessageSquare } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useStore } from "@/store";
import { useModels } from "@/hooks/useModels";
import { errMsg } from "@/lib/utils";
import { useToast } from "@/components/ui/use-toast";
import type { CloudModel } from "@/types";

interface CloudModelListProps {
  /** Bump to silently re-fetch models (e.g. after a provider is added/removed). */
  refreshKey?: number;
}

export function CloudModelList({ refreshKey = 0 }: CloudModelListProps) {
  const [models, setModels] = useState<CloudModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const { systemStatus, setSettingsOpen } = useStore();
  const { loadingId, loadModel } = useModels();
  const { toast } = useToast();

  // First load shows the spinner; provider-change refreshes (refreshKey) stay
  // silent — live provider fetches can take seconds and shouldn't blank the tab.
  const loadedOnce = useRef(false);
  const refresh = async (silent = false) => {
    if (!silent) setLoading(true);
    setRefreshing(true);
    try {
      const res = await api.listCloudModels();
      setModels(res.models || []);
      loadedOnce.current = true;
    } catch (error) {
      toast({
        title: "Failed to load cloud models",
        description: errMsg(error),
        variant: "destructive",
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    refresh(loadedOnce.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground">
        <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Loading online models...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cloud className="h-4 w-4 text-blue-400" />
          <h3 className="text-sm font-semibold">Online Models</h3>
          <Badge variant="secondary" className="text-xs">
            {models.length}
          </Badge>
        </div>
        <Button variant="ghost" size="sm" onClick={() => refresh(true)} disabled={refreshing}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {models.length === 0 ? (
        <div className="text-center py-6 text-muted-foreground border border-dashed border-border/60 rounded-lg">
          <p>No online models available.</p>
          <p className="text-sm mt-1 mb-3">
            Add a provider API key to use frontier models without local downloads.
          </p>
          <Button size="sm" variant="outline" onClick={() => setSettingsOpen('cloud')}>
            <Settings className="h-3.5 w-3.5 mr-1" />
            Open Settings → Cloud / Online
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {models.map((m) => (
            <div
              key={m.id}
              className="flex items-center gap-3 p-3 rounded-lg border border-border/60 bg-card hover:bg-accent/40 transition-colors"
            >
              <Cloud className="h-4 w-4 text-blue-400 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate">{m.name}</span>
                  <Badge variant="outline" className="text-[10px] shrink-0">
                    {m.provider_type}
                  </Badge>
                  {systemStatus?.current_model === m.id && (
                    <Badge className="text-[10px] bg-emerald-500/15 text-emerald-500 border-emerald-500/30 shrink-0">
                      In use
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {m.context_window ? `${m.context_window.toLocaleString()} ctx` : "context n/a"}
                  {!m.supports_streaming && " · no streaming"}
                </div>
              </div>
              {systemStatus?.current_model === m.id ? (
                <Link href="/">
                  <Button size="sm" variant="outline" className="gap-1 shrink-0">
                    <MessageSquare className="h-4 w-4" />
                    <span className="hidden sm:inline">Chat</span>
                  </Button>
                </Link>
              ) : (
                <Button
                  size="sm"
                  onClick={() => loadModel(m.id, "cloud")}
                  disabled={loadingId !== null}
                >
                  {loadingId === m.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  <span className="ml-1 hidden sm:inline">Load</span>
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}