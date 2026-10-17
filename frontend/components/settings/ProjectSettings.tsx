"use client";

import React, { useState } from "react";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Save, ExternalLink } from "lucide-react";
import { API_BASE } from "@/lib/apiBase";

interface ProjectSettingsProps {
  data: Record<string, unknown>;
  onSave: (data: Record<string, unknown>) => void;
}

export function ProjectSettings({ data, onSave }: ProjectSettingsProps) {
  const [form, setForm] = useState({
    project_name: "SovereignAI",
    project_version: "1.0.0",
    project_description: "",
    author: "",
    github_repo: "",
    environment: "development",
    api_endpoint: API_BASE,
    documentation_url: "",
    ...data,
  });

  // ponytail: React-blessed "adjust state during render" — replaces the old
  // useEffect(() => setForm(...), [data]) sync without the set-state-in-effect rule hit
  const [prevData, setPrevData] = useState(data);
  if (prevData !== data) {
    setPrevData(data);
    setForm((prev) => ({ ...prev, ...data }));
  }

  const update = (key: string, value: unknown) => {
    setForm((prev) => ({ ...prev, [key]: value }) as typeof form);
  };

  return (
    <div className="space-y-6">
      {/* Project Info */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Project Information
        </h3>

        <div className="space-y-2">
          <Label className="text-sm text-foreground">Project Name</Label>
          <Input
            className="bg-card border-input"
            value={form.project_name}
            onChange={(e) => update("project_name", e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label className="text-sm text-foreground">Version</Label>
            <Input
              className="bg-card border-input"
              value={form.project_version}
              onChange={(e) => update("project_version", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label className="text-sm text-foreground">Environment</Label>
            <Input
              className="bg-card border-input"
              value={form.environment}
              onChange={(e) => update("environment", e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label className="text-sm text-foreground">Description</Label>
          <Textarea
            className="bg-card border-input min-h-[100px]"
            value={form.project_description}
            onChange={(e) => update("project_description", e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label className="text-sm text-foreground">Author / Organization</Label>
          <Input
            className="bg-card border-input"
            value={form.author}
            onChange={(e) => update("author", e.target.value)}
          />
        </div>
      </div>

      {/* Connectivity */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Connectivity & Links
        </h3>

        <div className="space-y-2">
          <Label className="text-sm text-foreground">API Endpoint</Label>
          <Input
            className="bg-card border-input"
            value={form.api_endpoint}
            onChange={(e) => update("api_endpoint", e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label className="text-sm text-foreground">GitHub Repository</Label>
          <div className="flex gap-2">
            <Input
              className="bg-card border-input flex-1"
              value={form.github_repo}
              onChange={(e) => update("github_repo", e.target.value)}
            />
            {form.github_repo && (
              <Button
                variant="outline"
                size="icon"
                className="bg-card border-input hover:bg-muted"
                onClick={() => window.open(form.github_repo, "_blank")}
              >
                <ExternalLink className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <Label className="text-sm text-foreground">Documentation URL</Label>
          <div className="flex gap-2">
            <Input
              className="bg-card border-input flex-1"
              value={form.documentation_url}
              onChange={(e) => update("documentation_url", e.target.value)}
            />
            {form.documentation_url && (
              <Button
                variant="outline"
                size="icon"
                className="bg-card border-input hover:bg-muted"
                onClick={() => window.open(form.documentation_url, "_blank")}
              >
                <ExternalLink className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>

      <Button
        onClick={() => onSave(form)}
        className="w-full bg-primary hover:bg-primary/90"
      >
        <Save className="h-4 w-4 mr-2" />
        Sync Project Settings
      </Button>
    </div>
  );
}
