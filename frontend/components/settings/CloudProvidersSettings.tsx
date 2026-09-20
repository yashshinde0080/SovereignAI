"use client";

import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2, PlugZap, Loader2, Cloud } from "lucide-react";

import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";
import { errMsg } from "@/lib/utils";
import type { CloudProvider, CloudProviderType } from "@/types";

const PROVIDER_TYPES: { value: CloudProviderType; label: string; defaultBase?: string }[] = [
  { value: "openai", label: "OpenAI", defaultBase: "https://api.openai.com/v1" },
  { value: "anthropic", label: "Anthropic", defaultBase: "https://api.anthropic.com" },
  { value: "google", label: "Google Gemini", defaultBase: "https://generativelanguage.googleapis.com" },
  { value: "mistral", label: "Mistral", defaultBase: "https://api.mistral.ai/v1" },
  { value: "custom", label: "Custom (OpenAI-compatible)", defaultBase: "" },
];

interface CloudProvidersSettingsProps {
  /** Notify parents after add/toggle/delete — e.g. to refresh the model list. */
  onChanged?: () => void;
}

export function CloudProvidersSettings({ onChanged }: CloudProvidersSettingsProps) {
  const [providers, setProviders] = useState<CloudProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    provider_type: "openai" as CloudProviderType,
    name: "",
    api_key: "",
    base_url: "",
  });
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const refresh = async () => {
    try {
      const res = await api.listCloudProviders();
      setProviders(res.providers || []);
    } catch (error) {
      toast({
        title: "Failed to load providers",
        description: errMsg(error),
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const typeLabel = (t: string) =>
    PROVIDER_TYPES.find((p) => p.value === t)?.label || t;

  const handleTypeChange = (t: CloudProviderType) => {
    const preset = PROVIDER_TYPES.find((p) => p.value === t);
    setForm((prev) => ({
      ...prev,
      provider_type: t,
      name: prev.name || t.charAt(0).toUpperCase() + t.slice(1),
      base_url: t === "custom" ? prev.base_url : preset?.defaultBase || "",
    }));
  };

  const handleAdd = async () => {
    if (!form.api_key.trim()) {
      toast({ title: "API key required", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      await api.addCloudProvider({
        name: form.name || form.provider_type,
        provider_type: form.provider_type,
        api_key: form.api_key.trim(),
        base_url: form.provider_type === "custom" ? form.base_url || null : null,
      });
      toast({ title: "Provider added", description: "Test it to verify the key works." });
      setShowForm(false);
      setForm({ provider_type: "openai", name: "", api_key: "", base_url: "" });
      refresh();
      onChanged?.();
    } catch (error) {
      toast({
        title: "Failed to add provider",
        description: errMsg(error),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (p: CloudProvider, enabled: boolean) => {
    try {
      await api.updateCloudProvider(p.id, { is_enabled: enabled });
      setProviders((prev) =>
        prev.map((x) => (x.id === p.id ? { ...x, is_enabled: enabled } : x))
      );
      onChanged?.();
    } catch (error) {
      toast({ title: "Update failed", description: errMsg(error), variant: "destructive" });
    }
  };

  const handleDelete = async (p: CloudProvider) => {
    if (!window.confirm(`Remove provider "${p.name}"? This deletes its stored API key.`)) return;
    try {
      await api.deleteCloudProvider(p.id);
      setProviders((prev) => prev.filter((x) => x.id !== p.id));
      toast({ title: "Provider removed", description: p.name });
      onChanged?.();
    } catch (error) {
      toast({ title: "Delete failed", description: errMsg(error), variant: "destructive" });
    }
  };

  const handleTest = async (p: CloudProvider) => {
    setTestingId(p.id);
    try {
      const result = await api.testCloudProvider(p.id);
      toast({
        title: result.ok ? "Connection OK" : "Connection failed",
        description: result.message,
        variant: result.ok ? "default" : "destructive",
      });
    } catch (error) {
      toast({ title: "Test failed", description: errMsg(error), variant: "destructive" });
    } finally {
      setTestingId(null);
    }
  };

  return (
    <div className="space-y-6 pb-6">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            Cloud / Online Providers
          </h3>
          <p className="text-xs text-slate-500 mt-1 sm:max-w-md">
            Connect external AI APIs (OpenAI, Anthropic, Gemini, custom endpoints).
            Keys are encrypted on your machine and never sent to the frontend.
          </p>
        </div>
        <Button
          size="sm"
          className="bg-blue-600 hover:bg-blue-700 shrink-0"
          onClick={() => setShowForm((v) => !v)}
        >
          <Plus className="h-4 w-4 mr-1" />
          {showForm ? "Cancel" : "Add Provider"}
        </Button>
      </div>

      {showForm && (
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-3">
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label className="text-sm text-slate-300">Provider Type</Label>
              <Select value={form.provider_type} onValueChange={(v) => handleTypeChange(v as CloudProviderType)}>
                <SelectTrigger className="bg-slate-900 border-slate-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-slate-700">
                  {PROVIDER_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-slate-300">Name</Label>
              <Input
                className="bg-slate-900 border-slate-700"
                placeholder="My OpenAI"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label className="text-sm text-slate-300">API Key</Label>
            <Input
              type="password"
              className="bg-slate-900 border-slate-700 font-mono"
              placeholder="sk-..."
              value={form.api_key}
              onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label className="text-sm text-slate-300">
              Base URL {form.provider_type !== "custom" && <span className="text-slate-500">(optional override)</span>}
            </Label>
            <Input
              className="bg-slate-900 border-slate-700 font-mono"
              placeholder={
                form.provider_type === "custom"
                  ? "http://localhost:11434/v1 (Ollama, vLLM, LiteLLM...)"
                  : PROVIDER_TYPES.find((t) => t.value === form.provider_type)?.defaultBase
              }
              value={form.base_url}
              onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
            />
            {form.provider_type === "custom" && (
              <p className="text-xs text-slate-500">
                Custom endpoints must be OpenAI-compatible (e.g. Ollama, vLLM, Groq, Together).
              </p>
            )}
          </div>
          <div className="flex justify-end">
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={handleAdd} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Plus className="h-4 w-4 mr-1" />}
              Save Provider
            </Button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8 text-slate-500">
          <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Loading providers...
        </div>
      ) : providers.length === 0 ? (
        <div className="text-center py-8 text-slate-500">
          <Cloud className="h-8 w-8 mx-auto mb-2 text-slate-600" />
          No cloud providers. Add an API key to use online models.
        </div>
      ) : (
        <div className="space-y-3">
          {providers.map((p) => (
            <div
              key={p.id}
              className="flex items-center gap-3 p-3 rounded-lg border border-slate-800 bg-slate-900/40"
            >
              <Cloud className="h-4 w-4 text-blue-400 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-200">{p.name}</span>
                  <Badge variant="outline" className="text-[10px]">
                    {typeLabel(p.provider_type)}
                  </Badge>
                </div>
                <div className="text-xs text-slate-500 font-mono truncate mt-0.5">
                  {p.api_key_masked || "no key"}
                  {p.base_url ? ` · ${p.base_url}` : ""}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="border-slate-700 text-slate-300 hover:bg-slate-800 shrink-0"
                onClick={() => handleTest(p)}
                disabled={testingId === p.id}
              >
                {testingId === p.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <PlugZap className="h-3.5 w-3.5" />
                )}
                <span className="ml-1 hidden sm:inline">Test</span>
              </Button>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-xs text-slate-500">{p.is_enabled ? "On" : "Off"}</span>
                <Switch checked={p.is_enabled} onCheckedChange={(v) => handleToggle(p, v)} />
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-slate-500 hover:text-red-400 hover:bg-red-950/20 shrink-0"
                onClick={() => handleDelete(p)}
                title="Remove provider"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}