'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { Message, RagSource } from '@/types';
import { errMsg } from '@/lib/utils';
import { useSettingsStore } from '@/store/settings';
import { filterByRetention, isHistoryEnabled, isSessionOnly } from '@/lib/chatRetention';

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

function getSessionId(): string {
  if (typeof window === 'undefined') return '';
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

function storage(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    // clear_on_exit (and session_only retention) → sessionStorage so data
    // dies with the tab natively; otherwise localStorage.
    const dc = useSettingsStore.getState().settings?.data_controls as Record<string, unknown> | undefined;
    return isSessionOnly(dc) ? window.sessionStorage : window.localStorage;
  } catch {
    return null;
  }
}

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

function loadMessages(): Message[] {
  if (typeof window === 'undefined') return [];
  try {
    const dc = useSettingsStore.getState().settings?.data_controls as Record<string, unknown> | undefined;
    if (!isHistoryEnabled(dc)) return []; // memory-only mode
    const raw = storage()?.getItem(STORAGE_KEY);
    if (!raw) return [];
    return filterByRetention(sanitizeMessages(JSON.parse(raw)), dc?.data_retention);
  } catch {
    return [];
  }
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef(messages);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Load settings once on mount so sampling defaults + send_on_enter are live.
  useEffect(() => {
    const s = useSettingsStore.getState();
    if (!s.settings && !s.loading) void s.load();
  }, []);

  useEffect(() => {
    const restored = loadMessages();
    if (restored.length > 0) {
      setMessages(restored);
      return;
    }
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
      // ignore
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || isLoading) return;
    const dc = useSettingsStore.getState().settings?.data_controls as Record<string, unknown> | undefined;
    if (!isHistoryEnabled(dc)) return; // save off → don't persist
    try {
      storage()?.setItem(
        STORAGE_KEY,
        JSON.stringify(
          messages
            .filter((m) => m.content.trim())
            .map((m) => ({ ...m, ts: m.ts ?? Date.now() }))
        )
      );
    } catch {
      // non-fatal
    }
  }, [messages, isLoading]);

  const runCompletion = useCallback(async (messagesToSend: Message[]) => {
    setMessages(messagesToSend);
    setIsLoading(true);

    // Saved general settings are the defaults; backend re-resolves request > saved > default.
    const general = (useSettingsStore.getState().settings?.general ?? {}) as Record<string, unknown>;
    const savedMaxTokens = Number(general.max_tokens);
    const savedTemp = Number(general.temperature);
    const savedTopP = Number(general.top_p);
    const sampling = {
      ...(Number.isFinite(savedMaxTokens) && savedMaxTokens > 0 ? { max_tokens: savedMaxTokens } : {}),
      ...(Number.isFinite(savedTemp) ? { temperature: savedTemp } : {}),
      ...(Number.isFinite(savedTopP) && savedTopP > 0 && savedTopP <= 1 ? { top_p: savedTopP } : {}),
    };

    let flushRaf: number | null = null;
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${API_BASE}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          messages: messagesToSend,
          stream: true,
          use_rag: true,
          ...sampling,
          model: messagesToSend[0]?.model,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const err = new Error(errorData.detail || 'Chat request failed');
        (err as Error & { status?: number }).status = response.status;
        throw err;
      }

      if (response.headers.get('Content-Type')?.includes('text/event-stream')) {
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        let assistantContent = '';
        let assistantModel = '';
        let buffer = '';
        const decoder = new TextDecoder();

        const patchLastMessage = (patch: Partial<Message>) => {
          setMessages((prev) => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              ...newMessages[newMessages.length - 1],
              ...patch,
            };
            return newMessages;
          });
        };

        const flush = () => {
          flushRaf = null;
          patchLastMessage({
            content: assistantContent,
            ...(assistantModel ? { model: assistantModel } : {}),
          });
        };
        const scheduleFlush = () => {
          if (flushRaf !== null) return;
          flushRaf = requestAnimationFrame(flush);
        };

        setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

        try {
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

                  const modelName = chunk.choices?.[0]?.delta?.model_name;
                  if (modelName && !assistantModel) assistantModel = modelName;

                  const token = chunk.choices?.[0]?.delta?.content || '';
                  if (token) {
                    assistantContent += token;
                    scheduleFlush();
                  }
                } catch (e) {
                  console.error('JSON parse error:', e, data);
                }
              }
            }
          }
        } catch (e) {
          if ((e as Error)?.name !== 'AbortError') throw e;
        }

        if (flushRaf !== null) {
          cancelAnimationFrame(flushRaf);
          flushRaf = null;
        }
        patchLastMessage({
          content: assistantContent,
          ...(assistantModel ? { model: assistantModel } : {}),
        });
      } else {
        const data = await response.json();
        const msg = data.choices?.[0]?.message || {};
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: msg.content || '', ...(data.model ? { model: data.model } : {}) },
        ]);
      }
    } catch (error) {
      if ((error as Error)?.name !== 'AbortError') {
        console.error('Chat error:', error);
        const status = (error as Error & { status?: number })?.status;
        const body =
          status === 507
            ? `${errMsg(error) || 'Not enough memory or disk space.'} \n\n**How to fix:** load a smaller quant (Q4_K_M), or switch mode (FullRAM ↔ LayerStream) — and make sure the drive has room for the model + swap cache.`
            : `**Error:** ${errMsg(error) || 'Sorry, an error occurred.'}`;
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: body },
        ]);
      }
    } finally {
      abortRef.current = null;
      if (flushRaf !== null) {
        cancelAnimationFrame(flushRaf);
        flushRaf = null;
      }
      setIsLoading(false);
    }
  }, []);

  const stop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;
    runCompletion([...messagesRef.current, { role: 'user', content: trimmed }]);
  }, [runCompletion]);

  const editAndResend = useCallback((index: number, content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;
    runCompletion([...messagesRef.current.slice(0, index), { role: 'user', content: trimmed }]);
  }, [runCompletion]);

  const regenerate = useCallback(() => {
    const current = messagesRef.current;
    let lastUserIndex = -1;
    for (let i = current.length - 1; i >= 0; i--) {
      if (current[i].role === 'user') {
        lastUserIndex = i;
        break;
      }
    }
    if (lastUserIndex === -1) return;
    runCompletion(current.slice(0, lastUserIndex + 1));
  }, [runCompletion]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

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
      lines.push(`## ${m.role === 'user' ? 'User' : 'Assistant'}`, '');
      lines.push(m.content, '');
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

  return {
    messages,
    isLoading,
    sendMessage,
    editAndResend,
    regenerate,
    stop,
    clearMessages,
    exportChat,
  };
}
