'use client';

import { useRef, useEffect } from 'react';
import { ChatWindow } from '@/components/chat/ChatWindow';
import { PromptInput } from '@/components/chat/PromptInput';
import { useChat } from '@/hooks/useChat';

interface ChatModuleProps {
  taskType: string;
  model: string;
}

export function ChatModule({ taskType, model }: ChatModuleProps) {
  const { messages, isLoading, sendMessage, clearMessages } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex flex-col h-full bg-background rounded-b-2xl">
      <div className="flex-1 flex flex-col overflow-hidden">
        <ChatWindow messages={messages} isLoading={isLoading} />
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 mx-auto w-full max-w-4xl bg-gradient-to-t from-background via-background to-transparent pt-6">
        <PromptInput onSend={sendMessage} disabled={isLoading} />
        <div className="text-center mt-3 text-xs text-muted-foreground font-medium">
          Task: {taskType === 'unknown' ? 'Generative Chat' : taskType.replace(/_/g, ' ')} | AI can make mistakes. Verify important information.

        </div>
      </div>
    </div>
  );
}
