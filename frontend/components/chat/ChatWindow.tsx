'use client';

import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageList } from './MessageList';
import { Message } from '@/types';

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
}

export function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  return (
    <ScrollArea className="flex-1 p-4">
      <MessageList messages={messages} />
      {isLoading && (
        <div className="flex items-center gap-2 text-muted-foreground mt-4">
          <div className="flex gap-1">
            <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
            <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
            <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
          </div>
          <span className="text-sm">Thinking...</span>
        </div>
      )}
    </ScrollArea>
  );
}