"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";
import { useStore } from "@/store";
import { errMsg } from "@/lib/utils";
import {
  Upload,
  Trash2,
  FileText,
  MessageSquare,
  Gauge,
  Loader2,
} from "lucide-react";
import Link from "next/link";

interface Doc {
  id: string;
  filename: string;
  chunks: number;
}

// Services available to online models too — RAG retrieval happens server-side in
// chat (the same path local models use), benchmarks run through the active engine.
export function OnlineServices() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <RagQuickPanel />
      <QuickBenchmark />
    </div>
  );
}

function RagQuickPanel() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const { toast } = useToast();

  const loadDocs = useCallback(async () => {
    try {
      const res = await api.listDocuments();
      setDocs((res.documents || []).map((d: Doc) => d));
    } catch (error) {
      toast({ title: "Failed to load documents", description: errMsg(error), variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadDocument(file);
      await loadDocs();
      toast({ title: "Document uploaded", description: file.name });
    } catch (error) {
      toast({ title: "Upload failed", description: errMsg(error), variant: "destructive" });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (doc: Doc) => {
    if (!window.confirm(`Delete "${doc.filename}" from the RAG index?`)) return;
    try {
      await api.deleteDocument(doc.id);
      setDocs((prev) => prev.filter((d) => d.id !== doc.id));
      toast({ title: "Document deleted", description: doc.filename });
    } catch (error) {
      toast({ title: "Delete failed", description: errMsg(error), variant: "destructive" });
    }
  };

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="h-4 w-4 text-primary" />
          RAG Documents
        </CardTitle>
        <CardDescription>
          Indexed docs are retrieved in chat automatically — with online or local
          models (no extra setup)
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <input type="file" id="online-rag-upload" className="hidden" accept=".txt,.pdf" onChange={handleUpload} />
          <label htmlFor="online-rag-upload" className="flex-1">
            <Button asChild variant="outline" className="w-full" disabled={uploading}>
              <span>
                {uploading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
                {uploading ? "Uploading..." : "Upload .txt / .pdf"}
              </span>
            </Button>
          </label>
          <Link href="/documents">
            <Button variant="ghost">Manage all</Button>
          </Link>
        </div>

        {loading ? (
          <p className="text-sm text-muted-foreground text-center py-4">Loading...</p>
        ) : docs.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4 border border-dashed border-border/60 rounded-lg">
            No documents indexed yet
          </p>
        ) : (
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {docs.map((doc) => (
              <div key={doc.id} className="flex items-center gap-2 p-2 rounded-md bg-muted/50 text-sm">
                <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <span className="flex-1 truncate font-medium">{doc.filename}</span>
                <Badge variant="outline" className="text-[10px]">{doc.chunks} chunks</Badge>
                <Link href={`/console?ask=${encodeURIComponent(doc.filename)}`} title="Ask about this document in chat">
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                    <MessageSquare className="h-3.5 w-3.5 text-primary" />
                  </Button>
                </Link>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={() => handleDelete(doc)}
                  title="Delete document"
                >
                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function QuickBenchmark() {
  const { systemStatus } = useStore();
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<{ tps: number; tokens: number; seconds: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const isCloud = systemStatus?.current_mode === "cloud";

  const run = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.runBenchmark(3, 100);
      const summary = res.summary || {};
      setResult({
        tps: summary.average_tokens_per_second || 0,
        tokens: summary.total_tokens || 0,
        seconds: summary.total_time_seconds || 0,
      });
      toast({ title: "Benchmark complete", description: `${res.model} (${res.mode})` });
    } catch (error) {
      const msg = errMsg(error);
      setError(msg);
      toast({ title: "Benchmark failed", description: msg, variant: "destructive" });
    } finally {
      setRunning(false);
    }
  };

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Gauge className="h-4 w-4 text-primary" />
          Quick Benchmark
        </CardTitle>
        <CardDescription>
          Measures the currently loaded model{isCloud ? " over the network (remote inference)" : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <Button onClick={run} disabled={running || !systemStatus?.model_loaded} className="flex-1">
            {running ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Gauge className="h-4 w-4 mr-2" />}
            {running ? "Running..." : "Run (3 × 100 tokens)"}
          </Button>
          {systemStatus?.model_loaded && (
            <Link href="/benchmark">
              <Button variant="ghost">Full page</Button>
            </Link>
          )}
        </div>
        {!systemStatus?.model_loaded && (
          <p className="text-xs text-muted-foreground">
            No model loaded. Load an online (or offline) model above to benchmark it.
          </p>
        )}
        {systemStatus?.model_loaded && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="secondary" className="text-[10px] max-w-[220px] truncate">
              {systemStatus.current_model}
            </Badge>
            <Badge variant={isCloud ? "default" : "outline"} className="text-[10px]">
              {isCloud ? "online" : systemStatus.current_mode}
            </Badge>
          </div>
        )}
        {result && (
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 rounded-md bg-muted">
              <p className="text-lg font-bold text-success">{result.tps.toFixed(2)}</p>
              <p className="text-[10px] text-muted-foreground uppercase">Avg TPS</p>
            </div>
            <div className="p-2 rounded-md bg-muted">
              <p className="text-lg font-bold">{result.tokens}</p>
              <p className="text-[10px] text-muted-foreground uppercase">Tokens</p>
            </div>
            <div className="p-2 rounded-md bg-muted">
              <p className="text-lg font-bold">{result.seconds.toFixed(1)}s</p>
              <p className="text-[10px] text-muted-foreground uppercase">Time</p>
            </div>
          </div>
        )}
        {error && <p className="text-xs text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}