'use client';

import { useState, useRef, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { ChatWindow } from '@/components/chat/ChatWindow';
import { PromptInput } from '@/components/chat/PromptInput';
import { ModeSwitcher } from '@/components/chat/ModeSwitcher';
import { useStore } from '@/store';
import { useChat } from '@/hooks/useChat';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertCircle } from 'lucide-react';
import Link from 'next/link';

export default function ChatPage() {
  const { systemStatus } = useStore();
  const { messages, isLoading, sendMessage, clearMessages } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  if (!systemStatus?.model_loaded) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card className="p-6 max-w-md">
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              No model is currently loaded. Please load a model first to start chatting.
            </AlertDescription>
          </Alert>
          <Link href="/models" className="mt-4 block">
            <Button className="w-full">Go to Models</Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">Chat</h1>
          <p className="text-sm text-muted-foreground">
            Model: {systemStatus.current_model} | Mode: {systemStatus.current_mode}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <ModeSwitcher />
          <Button variant="outline" onClick={clearMessages}>
            Clear Chat
          </Button>
        </div>
      </div>

      {/* Chat Window */}
      <Card className="flex-1 flex flex-col overflow-hidden">
        <ChatWindow messages={messages} isLoading={isLoading} />
        <div ref={messagesEndRef} />
        
        {/* Input */}
        <div className="border-t p-4">
          <PromptInput onSend={sendMessage} disabled={isLoading} />
        </div>
      </Card>
    </div>
  );
}