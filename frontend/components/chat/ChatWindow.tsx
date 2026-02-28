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
    <ScrollArea className="flex-1 w-full px-4 md:px-8 py-4">
      <div className="max-w-4xl mx-auto w-full">
        <MessageList messages={messages} />
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