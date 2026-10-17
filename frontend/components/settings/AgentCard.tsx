'use client';

import React from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Bot,
  Stethoscope,
  Code,
  Scale,
  GraduationCap,
  FlaskConical,
  PenTool,
  Heart,
  DollarSign,
  BarChart,
  Shield,
  ChefHat,
  Dumbbell,
  Megaphone,
  BookOpen,
  Brain,
  Briefcase,
  Cpu,
  BrainCircuit,
  Microscope,
  Power,
  Pencil,
  Trash2,
  Copy,
  Wrench,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Agent } from '@/types';

export const ICON_MAP: Record<string, React.ElementType> = {
  bot: Bot,
  stethoscope: Stethoscope,
  code: Code,
  scale: Scale,
  'graduation-cap': GraduationCap,
  flask: FlaskConical,
  'flask-conical': FlaskConical,
  'pen-tool': PenTool,
  heart: Heart,
  'dollar-sign': DollarSign,
  'bar-chart': BarChart,
  shield: Shield,
  'chef-hat': ChefHat,
  dumbbell: Dumbbell,
  megaphone: Megaphone,
  book: BookOpen,
  brain: Brain,
  briefcase: Briefcase,
  cpu: Cpu,
  'brain-circuit': BrainCircuit,
  microscope: Microscope,
};

interface AgentCardProps {
  agent: Agent;
  onActivate: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onToggleEnabled: () => void;
  onDelete: () => void;
}

export function AgentCard({
  agent,
  onActivate,
  onEdit,
  onDuplicate,
  onToggleEnabled,
  onDelete,
}: AgentCardProps) {
  const IconComponent = ICON_MAP[agent.icon] || Bot;
  const roleLabel = agent.job_title || agent.role.replace(/_/g, ' ');

  return (
    <Card
      className={cn(
        'p-4 border transition-colors',
        agent.is_active ? 'bg-accent/10 border-accent/40' : 'bg-card hover:border-accent/30'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div
            className={cn(
              'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
              agent.is_active ? 'bg-accent/20' : 'bg-muted'
            )}
          >
            <IconComponent
              className={cn(
                'h-5 w-5',
                agent.is_active ? 'text-accent' : 'text-muted-foreground'
              )}
            />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="text-sm font-semibold text-foreground truncate">{agent.name}</h4>
              {agent.is_active && (
                <Badge className="bg-accent/20 text-accent text-[10px] px-1.5 py-0">Active</Badge>
              )}
              {!agent.enabled && (
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                  Disabled
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground capitalize truncate">{roleLabel}</p>
            {agent.description && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{agent.description}</p>
            )}
            <div className="flex flex-wrap items-center gap-3 mt-2 text-[11px] text-muted-foreground">
              <span>Temp: {agent.temperature}</span>
              <span>Max: {agent.max_tokens.toLocaleString()}</span>
              {agent.preferred_model && <span className="truncate">Model: {agent.preferred_model}</span>}
              {agent.tool_permissions.length > 0 && (
                <span className="inline-flex items-center gap-1">
                  <Wrench className="h-3 w-3" />
                  {agent.tool_permissions.length}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {!agent.is_active && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-secondary-foreground"
              onClick={onActivate}
              disabled={!agent.enabled}
              title={
                agent.enabled
                  ? 'Make this the default agent (used when no agent is picked in Chat)'
                  : 'Enable this agent first'
              }
            >
              <Power className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={onToggleEnabled}
            title={agent.enabled ? 'Disable agent' : 'Enable agent'}
          >
            <span
              className={cn(
                'text-[10px] font-bold uppercase',
                agent.enabled && 'text-secondary-foreground'
              )}
            >
              {agent.enabled ? 'On' : 'Off'}
            </span>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={onDuplicate}
            title="Duplicate agent"
          >
            <Copy className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={onEdit}
            title="Edit"
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-destructive"
            onClick={onDelete}
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
}
