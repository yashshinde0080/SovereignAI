'use client';

import { useState, useCallback, useEffect } from 'react';
import { Message, RagSource } from '@/types';
import { errMsg } from '@/lib/utils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const SESSION_KEY = 'sovereignai.chat.sessionId';
const LEGACY_STORAGE_KEY = 'sovereignai.chat.messages.v1';

// Normalize persisted sources — older chats stored plain string filenames.
function normalizeSources(sources: unknown): RagSource[] | undefined {
  if (!Array.isArray(sources)) return undefined;
  const normalized = sources
    .map((s): RagSource | null => {
      if (typeof s === 'string') return { filename: s };
      if (s && typeof s === 'object' && typeof (s as Record<string, unknown>).filename === 'string') {
        const docId = (s as Record<string, unknown>).document_id;
        return {
          filename: (s as Record<string, unknown>).filename as string,
          document_id: typeof docId === 'string' ? docId : undefined,
        };
      }
      return null;
    })
    .filter((s): s is RagSource => s !== null);
  return normalized.length > 0 ? normalized : undefined;
}

// One session ID per browser tab (sessionStorage is per-tab), so concurrent
// tabs persist under separate localStorage keys and never overwrite each
// other. Survives refresh within the tab; closing the tab starts a fresh
// session.
function getSessionId(): string {
  if (typeof window === 'undefined') return ''; // SSR placeholder, never stored
  try {
    let id = window.sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = `chat-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      window.sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch {
    return '';
  }
}

const STORAGE_KEY = `sovereignai.chat.messages.${getSessionId()}`;

// Validate parsed JSON into a Message[] (shared by load + legacy migration).
function sanitizeMessages(parsed: unknown): Message[] {
  if (!Array.isArray(parsed)) return [];
  return parsed
    .filter(
      (m: unknown) =>
        m !== null &&
        typeof m === 'object' &&
        (m as Record<string, unknown>).role === 'user' &&
        typeof (m as Record<string, unknown>).content === 'string'
    )
    .map((m) => ({ ...m, sources: normalizeSources((m as Record<string, unknown>).sources) }));
}

// Restore any persisted history for this session. Browser only; SSR-safe.
function loadMessages(): Message[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return sanitizeMessages(JSON.parse(raw));
  } catch {
    return [];
  }
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Restore persisted history once on mount, after hydration, so SSR and the
  // first client render agree (avoids a hydration mismatch from localStorage).
  useEffect(() => {
    const restored = loadMessages();
    if (restored.length > 0) {
      setMessages(restored);
      return;
    }
    // One-time migration: the pre-multi-session single key. Load it, then the
    // persist effect writes it under this session's key; drop the legacy key.
    try {
      const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
      if (legacy) {
        const migrated = sanitizeMessages(JSON.parse(legacy));
        if (migrated.length > 0) {
          window.localStorage.removeItem(LEGACY_STORAGE_KEY);
          setMessages(migrated);
          return;
        }
      }
    } catch {
      // ignore migration failures — fresh session is fine
    }
  }, []);

  // Persist so the chat survives a page refresh. Skipped while streaming (one
  // synchronous localStorage write per token would jank long generations); the
  // final write happens when the stream completes and isLoading flips false.
  // Empty-content entries (streaming placeholders) are skipped regardless.
  useEffect(() => {
    if (typeof window === 'undefined' || isLoading) return;
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(messages.filter((m) => m.content.trim()))
      );
    } catch {
      // storage unavailable (private mode, quota) — non-fatal
    }
  }, [messages, isLoading]);

  const runCompletion = useCallback(async (messagesToSend: Message[]) => {
    setMessages(messagesToSend);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messagesToSend,
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

                // Handle Stream Metadata (Sources / RAG). Sources become
                // structured chips on the assistant message, not appended text.
                if (chunk.choices?.[0]?.delta?.rag_metadata) {
                  const sources = chunk.choices[0].delta.rag_metadata as RagSource[];
                  if (sources && sources.length > 0) {
                    const seen = new Set();
                    const uniqueSources = sources.filter((s: RagSource) => {
                      if (seen.has(s.filename)) return false;
                      seen.add(s.filename);
                      return true;
                    });

                    setMessages((prev) => {
                      const newMessages = [...prev];
                      newMessages[newMessages.length - 1] = {
                        ...newMessages[newMessages.length - 1],
                        content: assistantContent,
                        sources: uniqueSources,
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
    } catch (error) {
      console.error('Chat error:', error);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `**Error:** ${errMsg(error) || 'Sorry, an error occurred.'}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const sendMessage = useCallback((content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;
    runCompletion([...messages, { role: 'user', content: trimmed }]);
  }, [messages, runCompletion]);

  // Replace the user message at `index`, drop everything after it, re-run.
  const editAndResend = useCallback((index: number, content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;
    runCompletion([...messages.slice(0, index), { role: 'user', content: trimmed }]);
  }, [messages, runCompletion]);

  // Re-run the last exchange: keep history up to the last user message,
  // drop the trailing assistant reply, and re-run the completion.
  const regenerate = useCallback(() => {
    let lastUserIndex = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        lastUserIndex = i;
        break;
      }
    }
    if (lastUserIndex === -1) return;
    runCompletion(messages.slice(0, lastUserIndex + 1));
  }, [messages, runCompletion]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  // Download the conversation as a markdown file.
  const exportChat = useCallback(() => {
    const date = new Date();
    const stamp = date.toISOString().slice(0, 19).replace(/[:T]/g, '-');
    const lines: string[] = [
      '# SovereignAI Chat Export',
      '',
      `*Exported ${date.toLocaleString()}*`,
      '',
      '---',
      '',
    ];
    for (const m of messages) {
      if (!m.content.trim()) continue;
      lines.push(`## ${m.role === 'user' ? 'User' : 'Assistant'}`, '', m.content, '');
      if (m.sources?.length) {
        lines.push('**Sources Used:**', ...m.sources.map((s) => `- ${s.filename}`), '');
      }
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sovereignai-chat-${stamp}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [messages]);

  return { messages, isLoading, sendMessage, editAndResend, regenerate, clearMessages, exportChat };
}
