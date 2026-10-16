'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Bot, Check, ChevronDown, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Agent } from '@/types';

interface AgentSelectorProps {
  agents: Agent[];
  /** null = the plain assistant (no custom agent). */
  agentId: string | null;
  onSelect: (agentId: string | null) => void;
  /** Model currently loaded, so a preference mismatch can be flagged. */
  activeModel?: string;
  disabled?: boolean;
}

function roleLabel(agent: Agent): string {
  if (agent.job_title) return agent.job_title;
  return agent.role.replace(/_/g, ' ');
}

export function AgentSelector({
  agents,
  agentId,
  onSelect,
  activeModel,
  disabled,
}: AgentSelectorProps) {
  const selected = agents.find((a) => a.id === agentId) || null;
  const enabled = agents.filter((a) => a.enabled);
  const modelMismatch =
    !!selected?.preferred_model && !!activeModel && selected.preferred_model !== activeModel;

  return (
    <div className="flex items-center gap-2 min-w-0">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            disabled={disabled}
            className={cn(
              'h-8 max-w-[280px] gap-2 px-2.5 text-xs font-medium',
              selected && 'border-accent/40 bg-accent/10 text-foreground'
            )}
            title={selected ? `${selected.name} — ${roleLabel(selected)}` : 'Answering as the default assistant'}
          >
            <Bot className={cn('h-3.5 w-3.5 shrink-0', selected ? 'text-accent' : 'text-muted-foreground')} />
            <span className="truncate">{selected ? selected.name : 'No agent'}</span>
            {selected && (
              <span className="hidden truncate text-muted-foreground sm:inline">
                · {roleLabel(selected)}
              </span>
            )}
            <ChevronDown className="h-3 w-3 shrink-0 opacity-60" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="start" className="w-[280px]">
          <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Answer as
          </DropdownMenuLabel>
          <DropdownMenuItem onSelect={() => onSelect(null)} className="gap-2">
            <Bot className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0 flex-1 truncate">Default assistant</span>
            {!selected && <Check className="h-4 w-4 shrink-0 text-accent" />}
          </DropdownMenuItem>

          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Agents
          </DropdownMenuLabel>

          {agents.length === 0 && (
            <div className="px-2 py-2 text-xs text-muted-foreground">
              No agents configured. Create one in Settings → Agents.
            </div>
          )}

          {agents.map((agent) => {
            const isSelected = agent.id === agentId;
            return (
              <DropdownMenuItem
                key={agent.id}
                disabled={!agent.enabled}
                onSelect={() => onSelect(agent.id)}
                className="gap-2"
                title={agent.enabled ? agent.description : 'Disabled in Settings → Agents'}
              >
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className={cn('truncate text-sm', !agent.enabled && 'text-muted-foreground')}>
                      {agent.name}
                    </span>
                    {!agent.enabled && (
                      <Badge variant="secondary" className="px-1 py-0 text-[9px]">
                        Disabled
                      </Badge>
                    )}
                  </span>
                  <span className="block truncate text-[11px] text-muted-foreground">
                    {roleLabel(agent)}
                  </span>
                </span>
                {isSelected && <Check className="h-4 w-4 shrink-0 text-accent" />}
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      {selected?.preferred_model && (
        <span
          className="hidden items-center gap-1 text-[11px] text-muted-foreground md:inline-flex"
          title={
            modelMismatch
              ? `This agent prefers ${selected.preferred_model}; ${activeModel} is loaded. The loaded model answers.`
              : `Preferred model: ${selected.preferred_model}`
          }
        >
          <Sparkles className={cn('h-3 w-3', modelMismatch ? 'text-destructive' : 'text-muted-foreground')} />
          {selected.preferred_model}
        </span>
      )}

      {enabled.length === 0 && agents.length > 0 && (
        <span className="hidden text-[11px] text-muted-foreground sm:inline">
          All agents disabled
        </span>
      )}
    </div>
  );
}
