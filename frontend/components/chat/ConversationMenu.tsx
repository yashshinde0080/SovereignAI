'use client';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Check, History, MessageSquarePlus, Pencil, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Conversation } from '@/lib/conversations';

interface ConversationMenuProps {
  conversations: Conversation[];
  activeId: string;
  onNew: () => void;
  onOpen: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  disabled?: boolean;
}

function relativeStamp(ms: number): string {
  if (!ms) return '';
  const minutes = Math.round((Date.now() - ms) / 60000);
  if (minutes < 1) return 'now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function ConversationMenu({
  conversations,
  activeId,
  onNew,
  onOpen,
  onRename,
  onDelete,
  disabled,
}: ConversationMenuProps) {
  const active = conversations.find((c) => c.id === activeId);

  const handleRename = () => {
    if (!active) return;
    const next = window.prompt('Rename conversation', active.title);
    if (next === null) return;
    const clean = next.trim();
    if (clean) onRename(active.id, clean);
  };

  const handleDelete = () => {
    if (!active) return;
    if (!window.confirm(`Delete "${active.title}" and its saved messages? This cannot be undone.`)) return;
    onDelete(active.id);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          disabled={disabled}
          className="h-8 max-w-[220px] gap-2 px-2.5 text-xs text-muted-foreground hover:text-foreground"
          title="Switch conversation"
        >
          <History className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{active?.title || 'Conversation'}</span>
          <span className="shrink-0 text-[10px] opacity-70">{conversations.length}</span>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="w-[300px]">
        <DropdownMenuItem onSelect={onNew} className="gap-2">
          <MessageSquarePlus className="h-4 w-4 shrink-0 text-accent" />
          New conversation
        </DropdownMenuItem>

        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Saved conversations
        </DropdownMenuLabel>

        <div className="max-h-[260px] overflow-y-auto">
          {conversations.map((c) => (
            <DropdownMenuItem
              key={c.id}
              onSelect={() => onOpen(c.id)}
              className="gap-2"
              title={c.title}
            >
              <span className="min-w-0 flex-1">
                <span className={cn('block truncate text-sm', c.id === activeId && 'font-medium')}>
                  {c.title}
                </span>
                <span className="block text-[11px] text-muted-foreground">
                  {c.messages.length} message{c.messages.length === 1 ? '' : 's'}
                  {c.updatedAt ? ` · ${relativeStamp(c.updatedAt)}` : ''}
                </span>
              </span>
              {c.id === activeId && <Check className="h-4 w-4 shrink-0 text-accent" />}
            </DropdownMenuItem>
          ))}
        </div>

        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={handleRename} className="gap-2">
          <Pencil className="h-4 w-4 shrink-0" />
          Rename “{active?.title || 'conversation'}”
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={handleDelete}
          className="gap-2 text-destructive focus:text-destructive"
        >
          <Trash2 className="h-4 w-4 shrink-0" />
          Delete this conversation
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
