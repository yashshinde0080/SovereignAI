'use client';

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { Message, RagSource, Agent } from '@/types';
import { errMsg } from '@/lib/utils';
import { useSettingsStore } from '@/store/settings';
import {
  filterByRetention,
  isHistoryEnabled,
  isSessionOnly,
  isSessionExpired,
} from '@/lib/chatRetention';
import { encryptText, decryptText, isEncrypted } from '@/lib/chatCrypto';
import { playChime } from '@/lib/sounds';
import {
  CONVERSATIONS_KEY,
  LEGACY_SESSION_KEY_PREFIX,
  activeConversation,
  addConversation,
  clearConversation,
  createConversation,
  createStore,
  deleteConversation,
  parseStore,
  pruneEmpty,
  renameConversation,
  serializeStore,
  sortedConversations,
  withMessages,
  type Conversation,
  type ConversationStore,
} from '@/lib/conversations';
import { API_BASE } from '@/lib/apiBase';

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

function settingsSnap() {
  const s = useSettingsStore.getState().settings;
  return {
    dc: s?.data_controls as Record<string, unknown> | undefined,
    general: s?.general as Record<string, unknown> | undefined,
    parental: s?.parental_controls as Record<string, unknown> | undefined,
  };
}

/** clear_on_exit / session_only → sessionStorage (dies with tab natively). */
function storageArea(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return isSessionOnly(settingsSnap().dc) ? window.sessionStorage : window.localStorage;
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
        ((m as Record<string, unknown>).role === 'user' ||
          (m as Record<string, unknown>).role === 'assistant') &&
        typeof (m as Record<string, unknown>).content === 'string'
    )
    .map((m) => ({ ...(m as Message), sources: normalizeSources((m as Record<string, unknown>).sources) }));
}

/** Decrypt (if needed) and read one stored blob, or null when absent/broken. */
async function readStored(key: string, area: Storage): Promise<string | null> {
  let raw: string | null = null;
  try {
    raw = area.getItem(key);
  } catch {
    return null;
  }
  if (raw === null) return null;
  if (!isEncrypted(raw)) return raw;
  try {
    return await decryptText(raw);
  } catch {
    return null; // undecryptable = treat as absent
  }
}

/**
 * One-time import of the pre-multi-conversation blobs
 * (`sovereignai.chat.messages.<sessionId>` and the even older `...v1`).
 */
async function migrateLegacyConversations(area: Storage): Promise<ConversationStore> {
  const store = createStore();
  const keys: string[] = [];
  try {
    for (let i = 0; i < area.length; i++) {
      const key = area.key(i);
      if (key && key.startsWith(LEGACY_SESSION_KEY_PREFIX)) keys.push(key);
    }
  } catch {
    return store;
  }

  const messages: Message[] = [];
  for (const key of keys) {
    const text = await readStored(key, area);
    if (!text) continue;
    try {
      messages.push(...sanitizeMessages(JSON.parse(text)));
    } catch {
      // ignore a single unreadable legacy blob
    }
  }
  for (const key of keys) {
    try {
      area.removeItem(key);
    } catch {
      // non-fatal
    }
  }
  return messages.length > 0
    ? withMessages(store, store.activeId, messages)
    : store;
}

async function loadStore(): Promise<ConversationStore> {
  if (typeof window === 'undefined') return createStore();
  const area = storageArea();
  if (!area) return createStore();
  try {
    const { dc } = settingsSnap();
    if (!isHistoryEnabled(dc)) return createStore(); // memory-only mode
    const raw = await readStored(CONVERSATIONS_KEY, area);
    const store = raw === null ? await migrateLegacyConversations(area) : parseStore(raw);
    return pruneEmpty({
      ...store,
      items: store.items.map((c) => ({
        ...c,
        messages: filterByRetention(sanitizeMessages(c.messages), dc?.data_retention),
      })),
    });
  } catch {
    return createStore();
  }
}

/** Persist every conversation honoring save_chat_history / retention stamp / encryption. */
async function persistStore(store: ConversationStore): Promise<void> {
  const { dc } = settingsSnap();
  if (!isHistoryEnabled(dc)) return; // save off → don't persist
  const area = storageArea();
  if (!area) return;
  const now = Date.now();
  const pruned = pruneEmpty({
    ...store,
    items: store.items.map((c) => ({
      ...c,
      messages: c.messages
        .filter((m) => m.content.trim())
        .map((m) => ({ ...m, ts: m.ts ?? now })),
    })),
  });
  const json = serializeStore(pruned);
  try {
    if (dc?.encrypt_local_data === true) {
      area.setItem(CONVERSATIONS_KEY, await encryptText(json));
    } else {
      // Downgrade: overwrite any previously-encrypted blob with plaintext so
      // toggling the switch off leaves no unreadable ciphertext behind.
      area.setItem(CONVERSATIONS_KEY, json);
    }
  } catch {
    // non-fatal
  }
}

// ── notifications + sounds ──

function notifyReply(): void {
  try {
    const general = settingsSnap().general;
    if (general?.enable_notifications === false) return;
    if (!document.hidden) return; // only bother the user when tab is backgrounded
    const electron = (window as unknown as { electronAPI?: { showNotification?: (o: { title: string; body: string }) => void } }).electronAPI;
    if (electron?.showNotification) {
      electron.showNotification({ title: 'SovereignAI', body: 'Reply ready.' });
    } else if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('SovereignAI', { body: 'Reply ready.' });
    }
  } catch {
    // non-fatal
  }
}

function onGenerationDone(): void {
  notifyReply();
  try {
    const general = settingsSnap().general;
    if (general?.enable_sounds === true) playChime();
  } catch {
    // non-fatal
  }
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  /** Live tok/s of the last/ongoing generation (show_token_speed). */
  const [tokenSpeed, setTokenSpeed] = useState<number | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState('');
  const [loaded, setLoaded] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef(messages);
  // Single source of truth for the conversation store; state mirrors it for render.
  const storeRef = useRef<ConversationStore>(createStore());
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);
  const sessionStartRef = useRef(Date.now());

  const commit = useCallback((next: ConversationStore) => {
    // Drop empty threads (except the open one) on every write so repeatedly
    // pressing "New conversation" can't pile up blank entries in the switcher.
    const pruned = pruneEmpty(next);
    storeRef.current = pruned;
    setActiveId(pruned.activeId);
    setConversations(sortedConversations(pruned));
    return pruned;
  }, []);

  const commitAndPersist = useCallback(
    (next: ConversationStore) => {
      commit(next);
      void persistStore(next);
      return next;
    },
    [commit]
  );

  const currentAgentId = useCallback(
    () => activeConversation(storeRef.current)?.agentId ?? null,
    []
  );

  const showMessages = useCallback((msgs: Message[]) => {
    messagesRef.current = msgs;
    setMessages(msgs);
    setTokenSpeed(null);
  }, []);

  // Load settings, then restore the conversation store (settings decide
  // storage location, retention, and encryption).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const s = useSettingsStore.getState();
      if (!s.settings && !s.loading) {
        await s.load().catch(() => undefined);
      }
      const restored = await loadStore();
      if (cancelled) return;
      const next = commit(restored);
      showMessages(activeConversation(next)?.messages ?? []);
      setLoaded(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [commit, showMessages]);

  // Sync the visible messages back into the active conversation and persist.
  // Skipped while generating so a half-streamed reply is never written.
  useEffect(() => {
    if (typeof window === 'undefined' || !loaded || isLoading) return;
    const next = withMessages(storeRef.current, storeRef.current.activeId, messages);
    commit(next);
    void persistStore(next);
  }, [messages, isLoading, loaded, commit]);

  const runCompletion = useCallback(async (messagesToSend: Message[]) => {
    const { general, parental } = settingsSnap();

    // Parental max_session_duration_minutes: 0 = unlimited.
    if (isSessionExpired(parental, sessionStartRef.current)) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '**Session time limit reached.** The session duration cap from Parental Controls has expired — start a new session to continue.' },
      ]);
      return;
    }

    setMessages(messagesToSend);
    setIsLoading(true);
    setTokenSpeed(null);

    // Saved general settings are the defaults; backend re-resolves request >
    // agent > saved > default. With an agent selected we deliberately send no
    // sampling values so the agent's own temperature/token limit takes effect.
    const agentId = currentAgentId();
    const savedMaxTokens = Number(general?.max_tokens);
    const savedTemp = Number(general?.temperature);
    const savedTopP = Number(general?.top_p);
    const sampling = agentId
      ? {}
      : {
          ...(Number.isFinite(savedMaxTokens) && savedMaxTokens > 0 ? { max_tokens: savedMaxTokens } : {}),
          ...(Number.isFinite(savedTemp) ? { temperature: savedTemp } : {}),
          ...(Number.isFinite(savedTopP) && savedTopP > 0 && savedTopP <= 1 ? { top_p: savedTopP } : {}),
        };

    // stream_responses=false → one blocking request (uses the non-SSE branch).
    const wantStream = general?.stream_responses !== false;

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
          stream: wantStream,
          use_rag: true,
          ...sampling,
          agent_id: agentId,
          model: messagesToSend[0]?.model,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData?.error?.message || errorData.detail || 'Chat request failed';
        const err = new Error(typeof detail === 'string' ? detail : 'Chat request failed');
        (err as Error & { status?: number }).status = response.status;
        throw err;
      }

      if (wantStream && response.headers.get('Content-Type')?.includes('text/event-stream')) {
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        let assistantContent = '';
        let assistantModel = '';
        let tokenCount = 0;
        let buffer = '';
        const decoder = new TextDecoder();
        const genStart = performance.now();

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
          const elapsed = (performance.now() - genStart) / 1000;
          if (elapsed > 0.2 && tokenCount > 0) {
            setTokenSpeed(tokenCount / elapsed); // show_token_speed lives here
          }
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
                    tokenCount += 1;
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
        const elapsed = (performance.now() - genStart) / 1000;
        if (elapsed > 0.2 && tokenCount > 0) setTokenSpeed(tokenCount / elapsed);
        patchLastMessage({
          content: assistantContent,
          ...(assistantModel ? { model: assistantModel } : {}),
        });
        onGenerationDone();
      } else {
        const data = await response.json();
        const msg = data.choices?.[0]?.message || {};
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: msg.content || '', ...(data.model ? { model: data.model } : {}) },
        ]);
        onGenerationDone();
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
  }, [currentAgentId]);

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

  /** Clear the current conversation in place, keeping its id and agent. */
  const clearMessages = useCallback(() => {
    abortRef.current?.abort();
    commitAndPersist(clearConversation(storeRef.current, storeRef.current.activeId));
    showMessages([]);
  }, [commitAndPersist, showMessages]);

  /** Start a brand new conversation, optionally bound to an agent. */
  const newConversation = useCallback(
    (agentId: string | null = currentAgentId()) => {
      abortRef.current?.abort();
      commitAndPersist(addConversation(storeRef.current, createConversation(agentId)));
      showMessages([]);
    },
    [commitAndPersist, currentAgentId, showMessages]
  );

  /** Switch to another saved conversation; flushes the current one first. */
  const openConversation = useCallback(
    (id: string) => {
      const current = storeRef.current;
      if (id === current.activeId) return;
      const target = current.items.find((c) => c.id === id);
      if (!target) return;
      abortRef.current?.abort();
      const flushed = withMessages(current, current.activeId, messagesRef.current);
      const next = commitAndPersist({ ...flushed, activeId: id });
      showMessages(activeConversation(next)?.messages ?? []);
    },
    [commitAndPersist, showMessages]
  );

  const renameThread = useCallback(
    (id: string, title: string) => {
      commitAndPersist(renameConversation(storeRef.current, id, title));
    },
    [commitAndPersist]
  );

  const deleteThread = useCallback(
    (id: string) => {
      abortRef.current?.abort();
      const next = commitAndPersist(deleteConversation(storeRef.current, id));
      showMessages(activeConversation(next)?.messages ?? []);
    },
    [commitAndPersist, showMessages]
  );

  /**
   * Bind an agent to the conversation. An untouched (empty) thread just
   * rebinds; a thread with history in it starts a fresh conversation so the two
   * personas can never share instructions or messages.
   *
   * Returns true when a new conversation was created (the UI can say so).
   */
  const selectAgent = useCallback(
    (agentId: string | null): boolean => {
      const current = storeRef.current;
      const conv = activeConversation(current);
      if (!conv) return false;
      if (conv.agentId === agentId) return false;

      if (conv.messages.length === 0) {
        commitAndPersist({
          ...current,
          items: current.items.map((c) => (c.id === conv.id ? { ...c, agentId } : c)),
        });
        return false;
      }

      abortRef.current?.abort();
      commitAndPersist(addConversation(current, createConversation(agentId)));
      showMessages([]);
      return true;
    },
    [commitAndPersist, showMessages]
  );

  /** Drop agents that no longer exist from restored conversations. */
  const reconcileAgents = useCallback(
    (agents: Agent[]) => {
      const known = new Set(agents.map((a) => a.id));
      const current = storeRef.current;
      let changed = false;
      const items = current.items.map((c) => {
        if (c.agentId && !known.has(c.agentId)) {
          changed = true;
          return { ...c, agentId: null };
        }
        return c;
      });
      if (changed) commitAndPersist({ ...current, items });
    },
    [commitAndPersist]
  );

  const activeAgentId = useMemo(
    () => conversations.find((c) => c.id === activeId)?.agentId ?? null,
    [conversations, activeId]
  );

  // export_format (data_controls): json | csv | markdown (default).
  const exportChat = useCallback(() => {
    const date = new Date();
    const stamp = date.toISOString().slice(0, 19).replace(/[:T]/g, '-');
    const usable = messages.filter((m) => m.content.trim());
    const fmt = String(settingsSnap().dc?.export_format || 'markdown');
    let blob: Blob;
    let filename: string;

    if (fmt === 'json') {
      blob = new Blob(
        [JSON.stringify({ exported: date.toISOString(), messages: usable }, null, 2)],
        { type: 'application/json;charset=utf-8' }
      );
      filename = `sovereignai-chat-${stamp}.json`;
    } else if (fmt === 'csv') {
      const esc = (s: string) => `"${s.replace(/"/g, '""')}"`;
      const rows = ['role,content,sources'];
      for (const m of usable) {
        rows.push(
          [esc(m.role), esc(m.content), esc((m.sources ?? []).map((s) => s.filename).join('; '))].join(',')
        );
      }
      blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' });
      filename = `sovereignai-chat-${stamp}.csv`;
    } else {
      const lines: string[] = [
        '# SovereignAI Chat Export',
        '',
        `*Exported ${date.toLocaleString()}*`,
        '',
        '---',
        '',
      ];
      for (const m of usable) {
        lines.push(`## ${m.role === 'user' ? 'User' : 'Assistant'}`, '');
        lines.push(m.content, '');
        if (m.sources?.length) {
          lines.push('**Sources Used:**', ...m.sources.map((s) => `- ${s.filename}`), '');
        }
      }
      blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
      filename = `sovereignai-chat-${stamp}.md`;
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [messages]);

  return {
    messages,
    isLoading,
    tokenSpeed,
    conversations,
    activeConversationId: activeId,
    activeAgentId,
    sendMessage,
    editAndResend,
    regenerate,
    stop,
    clearMessages,
    newConversation,
    openConversation,
    renameThread,
    deleteThread,
    selectAgent,
    reconcileAgents,
    exportChat,
  };
}
