'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Plus, PowerOff, Loader2, AlertTriangle } from 'lucide-react';

import { AgentCard, ICON_MAP } from './AgentCard';

import { useToast } from '@/components/ui/use-toast';
import { api } from '@/lib/api';
import { errMsg } from '@/lib/utils';
import { AGENT_TOOLS } from '@/lib/agentTools';
import type { Agent } from '@/types';

// Labels for the role enum (backend AgentRole). The role is a coarse category;
// job_title is the free-text display name shown on top of it.
const ROLES = [
  { value: 'ceo', label: 'CEO (Chief Executive Officer)' },
  { value: 'cto', label: 'CTO (Chief Technology Officer)' },
  { value: 'software_engineer', label: 'Senior Software Engineer' },
  { value: 'ml_engineer', label: 'AI / ML Engineer' },
  { value: 'research_analyst', label: 'Research Analyst' },
  { value: 'doctor', label: 'Doctor' },
  { value: 'engineer', label: 'Engineer' },
  { value: 'lawyer', label: 'Lawyer' },
  { value: 'teacher', label: 'Teacher' },
  { value: 'scientist', label: 'Scientist' },
  { value: 'writer', label: 'Writer' },
  { value: 'therapist', label: 'Therapist' },
  { value: 'financial_advisor', label: 'Financial Advisor' },
  { value: 'chef', label: 'Chef' },
  { value: 'fitness_trainer', label: 'Fitness Trainer' },
  { value: 'data_analyst', label: 'Data Analyst' },
  { value: 'marketing_expert', label: 'Marketing Expert' },
  { value: 'cybersecurity_expert', label: 'Cybersecurity Expert' },
  { value: 'historian', label: 'Historian' },
  { value: 'philosopher', label: 'Philosopher' },
  { value: 'custom', label: 'Custom' },
];

const ICONS = Object.keys(ICON_MAP);

interface AgentForm {
  id: string;
  name: string;
  role: string;
  job_title: string;
  description: string;
  system_instruction: string;
  responsibilities: string;
  preferred_model: string;
  welcome_message: string;
  tool_permissions: string[];
  icon: string;
  temperature: number;
  max_tokens: number;
  enabled: boolean;
  is_active: boolean;
}

const EMPTY_FORM: AgentForm = {
  id: '',
  name: '',
  role: 'custom',
  job_title: '',
  description: '',
  system_instruction: '',
  responsibilities: '',
  preferred_model: '',
  welcome_message: '',
  tool_permissions: [],
  icon: 'bot',
  temperature: 0.7,
  max_tokens: 2048,
  enabled: true,
  is_active: false,
};

/** The backend requires ids matching ^[A-Za-z0-9_-]{1,64}$. */
function newAgentId(name: string): string {
  const slug =
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 32) || 'agent';
  return `agent_${slug}_${Date.now().toString(36)}`;
}

function toForm(agent: Agent): AgentForm {
  return {
    id: agent.id,
    name: agent.name,
    role: agent.role,
    job_title: agent.job_title,
    description: agent.description,
    system_instruction: agent.system_instruction,
    responsibilities: agent.responsibilities,
    preferred_model: agent.preferred_model,
    welcome_message: agent.welcome_message,
    tool_permissions: agent.tool_permissions,
    icon: agent.icon,
    temperature: agent.temperature,
    max_tokens: agent.max_tokens,
    enabled: agent.enabled,
    is_active: agent.is_active,
  };
}

interface AgentSettingsProps {
  agents: Agent[];
  onRefresh: () => void;
}

export function AgentSettings({ agents, onRefresh }: AgentSettingsProps) {
  const [createOpen, setCreateOpen] = useState(false);
  const [editAgent, setEditAgent] = useState<Agent | null>(null);
  const [form, setForm] = useState<AgentForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [modelOptions, setModelOptions] = useState<{ value: string; label: string }[]>([
    { value: '', label: 'Use the loaded model' },
  ]);
  const { toast } = useToast();

  // Preferred-model choices: installed local models + configured cloud models.
  // Both endpoints are optional infrastructure — a failure leaves the always
  // valid "use the loaded model" option.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const options = [{ value: '', label: 'Use the loaded model' }];
      try {
        const res = await api.listModels();
        for (const m of res.models || []) options.push({ value: m.name, label: m.name });
      } catch {
        // no model registry reachable
      }
      try {
        const res = await api.listCloudModels();
        for (const m of res.models || []) options.push({ value: m.id, label: `${m.name} (cloud)` });
      } catch {
        // cloud providers not configured
      }
      if (!cancelled) setModelOptions(options);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const updateForm = (key: keyof AgentForm, value: unknown) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const nameTaken = useMemo(
    () =>
      form.name.trim().length > 0 &&
      agents.some(
        (a) => a.id !== form.id && a.name.trim().toLowerCase() === form.name.trim().toLowerCase()
      ),
    [agents, form.id, form.name]
  );

  const nameError = !form.name.trim()
    ? 'Name is required.'
    : nameTaken
      ? 'Another agent already uses this name.'
      : '';
  const instructionError = !form.system_instruction.trim()
    ? 'System instructions are required — this is what makes the agent behave as its role.'
    : '';
  const canSave = !nameError && !instructionError && !saving;

  const payload = (): Agent => ({
    id: form.id,
    name: form.name.trim(),
    role: form.role,
    job_title: form.job_title.trim(),
    description: form.description.trim(),
    system_instruction: form.system_instruction.trim(),
    responsibilities: form.responsibilities.trim(),
    preferred_model: form.preferred_model,
    welcome_message: form.welcome_message.trim(),
    tool_permissions: form.tool_permissions,
    icon: form.icon,
    temperature: form.temperature,
    max_tokens: form.max_tokens,
    enabled: form.enabled,
    is_active: form.is_active,
  });

  // Keep a model the backend no longer lists visible (removed since saving)
  // instead of silently resetting the agent to "use the loaded model".
  const modelChoices = useMemo(() => {
    const values = new Set(modelOptions.map((o) => o.value));
    if (form.preferred_model && !values.has(form.preferred_model)) {
      return [
        ...modelOptions,
        { value: form.preferred_model, label: `${form.preferred_model} (not installed)` },
      ];
    }
    return modelOptions;
  }, [modelOptions, form.preferred_model]);

  const openCreate = () => {
    setForm({ ...EMPTY_FORM });
    setCreateOpen(true);
  };

  const openEdit = (agent: Agent) => {
    setForm(toForm(agent));
    setEditAgent(agent);
  };

  const handleCreate = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      await api.createAgent({ ...payload(), id: newAgentId(form.name.trim()) });
      toast({ title: 'Created', description: `Agent '${form.name.trim()}' created` });
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      onRefresh();
    } catch (error) {
      toast({ title: 'Could not create agent', description: errMsg(error), variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!canSave || !editAgent) return;
    setSaving(true);
    try {
      await api.updateAgent(editAgent.id, payload());
      toast({ title: 'Updated', description: `Agent '${form.name.trim()}' saved` });
      setEditAgent(null);
      setForm(EMPTY_FORM);
      onRefresh();
    } catch (error) {
      toast({ title: 'Could not save agent', description: errMsg(error), variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (agent: Agent) => {
    if (!window.confirm(`Delete agent "${agent.name}"? This cannot be undone.`)) return;
    try {
      await api.deleteAgent(agent.id);
      toast({ title: 'Deleted', description: `Agent '${agent.name}' removed` });
      onRefresh();
    } catch (error) {
      toast({ title: 'Could not delete agent', description: errMsg(error), variant: 'destructive' });
    }
  };

  const handleDuplicate = async (agent: Agent) => {
    try {
      await api.duplicateAgent(agent.id);
      toast({ title: 'Duplicated', description: `${agent.name} (copy) created` });
      onRefresh();
    } catch (error) {
      toast({
        title: 'Could not duplicate agent',
        description: errMsg(error),
        variant: 'destructive',
      });
    }
  };

  const handleToggleEnabled = async (agent: Agent) => {
    try {
      await api.updateAgent(agent.id, { ...agent, enabled: !agent.enabled });
      onRefresh();
    } catch (error) {
      toast({ title: 'Could not update agent', description: errMsg(error), variant: 'destructive' });
    }
  };

  const handleActivate = async (agent: Agent) => {
    try {
      await api.activateAgent(agent.id);
      toast({ title: 'Activated', description: `'${agent.name}' is now the default agent` });
      onRefresh();
    } catch (error) {
      toast({
        title: 'Could not activate agent',
        description: errMsg(error),
        variant: 'destructive',
      });
    }
  };

  const handleDeactivateAll = async () => {
    try {
      await api.deactivateAllAgents();
      toast({ title: 'Deactivated', description: 'All agents deactivated' });
      onRefresh();
    } catch (error) {
      toast({
        title: 'Could not deactivate',
        description: errMsg(error),
        variant: 'destructive',
      });
    }
  };

  const agentFormDialog = (isEdit: boolean, open: boolean, onClose: () => void) => (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-h-[85vh] max-w-[680px] overflow-y-auto bg-background text-foreground">
        <DialogHeader className="pr-8">
          <DialogTitle>{isEdit ? 'Edit Agent' : 'Create New Agent'}</DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Save the agent here, then pick it in Chat or Console to answer as that role.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-sm text-foreground">Name</Label>
              <Input
                className="bg-card border-input"
                placeholder="Agent name"
                value={form.name}
                onChange={(e) => updateForm('name', e.target.value)}
                aria-invalid={!!nameError}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-foreground">Job Title</Label>
              <Input
                className="bg-card border-input"
                placeholder="e.g. Chief Executive Officer"
                value={form.job_title}
                onChange={(e) => updateForm('job_title', e.target.value)}
              />
            </div>
          </div>
          {nameError && <p className="text-xs text-destructive">{nameError}</p>}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-sm text-foreground">Role</Label>
              <Select value={form.role} onValueChange={(v) => updateForm('role', v)}>
                <SelectTrigger className="bg-card border-input">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-foreground">Icon</Label>
              <Select value={form.icon} onValueChange={(v) => updateForm('icon', v)}>
                <SelectTrigger className="bg-card border-input">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-[240px]">
                  {ICONS.map((i) => (
                    <SelectItem key={i} value={i}>
                      {i}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-sm text-foreground">Description</Label>
            <Textarea
              className="min-h-[60px] bg-card border-input"
              placeholder="Brief description of this agent's purpose"
              value={form.description}
              onChange={(e) => updateForm('description', e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label className="text-sm text-foreground">System Instructions (personality)</Label>
            <p className="text-xs text-muted-foreground">
              Sent to the model as this agent&apos;s system prompt. Define how it reasons and what
              shape its answers take.
            </p>
            <Textarea
              className="min-h-[170px] bg-card border-input font-mono text-sm"
              placeholder="You are the Chief Executive Officer. You reason in terms of business impact, cost, timelines, and measurable outcomes..."
              value={form.system_instruction}
              onChange={(e) => updateForm('system_instruction', e.target.value)}
              aria-invalid={!!instructionError}
            />
            {instructionError && <p className="text-xs text-destructive">{instructionError}</p>}
          </div>

          <div className="space-y-2">
            <Label className="text-sm text-foreground">Responsibilities &amp; Objectives</Label>
            <Textarea
              className="min-h-[90px] bg-card border-input text-sm"
              placeholder="- Own company strategy and priorities&#10;- Decide where to invest&#10;- Turn goals into measurable plans"
              value={form.responsibilities}
              onChange={(e) => updateForm('responsibilities', e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label className="text-sm text-foreground">Welcome Message (optional)</Label>
            <Input
              className="bg-card border-input"
              placeholder="Shown in Chat before the first message"
              value={form.welcome_message}
              onChange={(e) => updateForm('welcome_message', e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label className="text-sm text-foreground">Preferred Model</Label>
            <Select
              value={form.preferred_model}
              onValueChange={(v) => updateForm('preferred_model', v)}
            >
              <SelectTrigger className="w-full bg-card border-input">
                <SelectValue placeholder="Use the loaded model" />
              </SelectTrigger>
              <SelectContent>
                {modelChoices.map((m) => (
                  <SelectItem key={m.value || '__none'} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Loaded when no model is running yet. A model that is already loaded always answers.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-sm text-foreground">
                Temperature: {form.temperature.toFixed(1)}
              </Label>
              <Slider
                min={0}
                max={2}
                step={0.1}
                value={[form.temperature]}
                onValueChange={(v) => updateForm('temperature', v[0])}
              />
              <p className="text-xs text-muted-foreground">
                Lower = more focused. Higher = more creative.
              </p>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-foreground">Max Output Tokens</Label>
              <Input
                type="number"
                className="bg-card border-input"
                min={64}
                max={32768}
                step={256}
                value={form.max_tokens}
                onChange={(e) => {
                  const n = parseInt(e.target.value, 10);
                  updateForm(
                    'max_tokens',
                    Number.isFinite(n) ? Math.min(32768, Math.max(64, n)) : 2048
                  );
                }}
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label className="text-sm text-foreground">Tool Permissions</Label>
              <Badge variant="outline" className="text-[10px]">
                Foundation
              </Badge>
            </div>
            <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-2.5 text-xs text-muted-foreground">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
              <span>
                No tool executes yet — agents cannot read files, run code, or reach your system.
                Selections are stored on the agent and validated by the backend.
              </span>
            </div>
            <div className="space-y-2">
              {AGENT_TOOLS.map((tool) => (
                <div key={tool.id} className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm text-foreground">{tool.label}</span>
                      {!tool.available && (
                        <Badge variant="secondary" className="text-[9px]">
                          Not available yet
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">{tool.description}</p>
                  </div>
                  <Switch
                    checked={form.tool_permissions.includes(tool.id)}
                    onCheckedChange={(v) =>
                      updateForm(
                        'tool_permissions',
                        v
                          ? [...form.tool_permissions, tool.id]
                          : form.tool_permissions.filter((t) => t !== tool.id)
                      )
                    }
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2">
            <div>
              <Label className="text-sm text-foreground">Enabled</Label>
              <p className="text-xs text-muted-foreground">
                Only enabled agents can be selected for a new conversation.
              </p>
            </div>
            <Switch checked={form.enabled} onCheckedChange={(v) => updateForm('enabled', v)} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={isEdit ? handleUpdate : handleCreate} disabled={!canSave}>
            {saving && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
            {isEdit ? 'Update Agent' : 'Create Agent'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  return (
    <div className="space-y-6 pb-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground">
            AI Agents
          </h3>
          <p className="mt-1 text-xs text-muted-foreground sm:max-w-md">
            Agents are saved instructions sent to your model. Select one in Chat or Console and it
            answers as that role.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={handleDeactivateAll}>
            <PowerOff className="mr-1 h-4 w-4" />
            Deactivate All
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="mr-1 h-4 w-4" />
            New Agent
          </Button>
        </div>
      </div>

      <div className="grid gap-3">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            onActivate={() => handleActivate(agent)}
            onEdit={() => openEdit(agent)}
            onDuplicate={() => handleDuplicate(agent)}
            onToggleEnabled={() => handleToggleEnabled(agent)}
            onDelete={() => handleDelete(agent)}
          />
        ))}
      </div>

      {agents.length === 0 && (
        <div className="py-8 text-center text-muted-foreground">
          No agents configured. Create your first agent.
        </div>
      )}

      {agentFormDialog(false, createOpen, () => {
        setCreateOpen(false);
        setForm(EMPTY_FORM);
      })}

      {agentFormDialog(true, !!editAgent, () => {
        setEditAgent(null);
        setForm(EMPTY_FORM);
      })}
    </div>
  );
}
