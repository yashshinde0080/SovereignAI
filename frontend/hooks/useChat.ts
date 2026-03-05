'use client';

import { useState, useCallback } from 'react';
import { Message } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim()) return;
    
    const userMessage: Message = { role: 'user', content };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: updatedMessages,
          stream: true,
          use_rag: true,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Chat request failed');
      }

      if (response.headers.get('Content-Type')?.includes('text/event-stream')) {
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        let assistantContent = '';
        let buffer = '';
        const decoder = new TextDecoder();

        // Add placeholder message
        setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim();
              if (data === '[DONE]') continue;

              try {
                const chunk = JSON.parse(data);
                
                // Handle Stream Metadata (Sources / RAG)
                if (chunk.choices?.[0]?.delta?.rag_metadata) {
                  const sources = chunk.choices[0].delta.rag_metadata;
                  if (sources && sources.length > 0) {
                    const seen = new Set();
                    const uniqueSources = sources.filter((s: any) => {
                      if (seen.has(s.filename)) return false;
                      seen.add(s.filename);
                      return true;
                    });
                    assistantContent += '\n\n**Sources Used:**\n' + uniqueSources.map((s: any) => `- ${s.filename}`).join('\n');
                    
                    setMessages((prev) => {
                      const newMessages = [...prev];
                      newMessages[newMessages.length - 1] = {
                        role: 'assistant',
                        content: assistantContent,
                      };
                      return newMessages;
                    });
                  }
                  continue;
                }

                const token = chunk.choices?.[0]?.delta?.content || '';
                if (token) {
                  assistantContent += token;

                  setMessages((prev) => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1] = {
                      role: 'assistant',
                      content: assistantContent,
                    };
                    return newMessages;
                  });
                }
              } catch (e) {
                console.error('JSON parse error:', e, data);
              }
            }
          }
        }
      } else {
        // Fallback for non-streaming
        const data = await response.json();
        const content = data.choices?.[0]?.message?.content || "";
        setMessages((prev) => [...prev, { role: 'assistant', content }]);
      }
    } catch (error: any) {
      console.error('Chat error:', error);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `**Error:** ${error.message || 'Sorry, an error occurred.'}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [messages]);


  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, isLoading, sendMessage, clearMessages };
}