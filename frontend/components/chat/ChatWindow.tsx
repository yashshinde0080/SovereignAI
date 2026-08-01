'use client';

import { useEffect, useRef } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageList } from './MessageList';
import { Message } from '@/types';

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
  editingIndex?: number | null;
  onEditMessage?: (index: number) => void;
  onRegenerate?: () => void;
}

export function ChatWindow({ messages, isLoading, editingIndex, onEditMessage, onRegenerate }: ChatWindowProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  // Auto-scroll to the newest message while streaming, unless the user has
  // scrolled up to read history (stickToBottom flips off on manual scroll).
  // Submitting a new message always jumps back to the bottom.
  useEffect(() => {
    const viewport = viewportRef.current;
    if (messages[messages.length - 1]?.role === 'user') {
      stickToBottom.current = true;
    }
    if (viewport && stickToBottom.current) {
      viewport.scrollTop = viewport.scrollHeight;
    }
  }, [messages, isLoading]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const onScroll = () => {
      const distanceFromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
      stickToBottom.current = distanceFromBottom < 80;
    };
    viewport.addEventListener('scroll', onScroll, { passive: true });
    return () => viewport.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <ScrollArea
      viewportRef={viewportRef}
      type="always"
      className="flex-1 min-h-0 w-full px-4 md:px-8 py-4"
      scrollBarClassName="w-1.5"
      thumbClassName="bg-brand/70 hover:bg-brand active:bg-brand-accent transition-colors"
    >
      <div className="max-w-4xl mx-auto w-full">
        <MessageList
          messages={messages}
          onEditMessage={onEditMessage}
          onRegenerate={onRegenerate}
          editingIndex={editingIndex}
          isLoading={isLoading}
        />
        {isLoading && (
          <div className="flex items-center gap-3 text-muted-foreground mt-4 mb-8">
            <div className="flex gap-1.5 px-3 py-2.5 bg-muted/50 rounded-2xl w-fit">
              <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
              <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
              <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
            </div>
          </div>
        )}
      </div>
    </ScrollArea>
  );
}