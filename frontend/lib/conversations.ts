// Conversation bookkeeping for chat, kept pure so it is node-testable without
// React or the DOM. Storage I/O lives in useChat, which already owns the
// retention/encryption rules from data_controls.
//
// A conversation is bound to exactly one agent for its whole lifetime: there is
// no per-message agent field, so two personas can never mix inside one thread.

import type { Message } from '@/types';

export interface Conversation {
  id: string;
  title: string;
  /** null = the plain assistant (no agent selected). */
  agentId: string | null;
  messages: Message[];
  updatedAt: number;
  /** Set once the user renames the thread — the auto title stops updating. */
  renamed?: boolean;
}

export interface ConversationStore {
  activeId: string;
  items: Conversation[];
}

export const CONVERSATIONS_KEY = 'sovereignai.chat.conversations.v1';
/** Pre-multi-conversation per-tab blob, imported once then removed. */
export const LEGACY_SESSION_KEY_PREFIX = 'sovereignai.chat.messages.';

export const DEFAULT_TITLE = 'New chat';
export const MAX_TITLE_CHARS = 48;

export function newConversationId(now: number = Date.now()): string {
  return `conv-${now.toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function createConversation(
  agentId: string | null = null,
  now: number = Date.now()
): Conversation {
  return {
    id: newConversationId(now),
    title: DEFAULT_TITLE,
    agentId,
    messages: [],
    updatedAt: now,
  };
}

export function createStore(agentId: string | null = null, now: number = Date.now()): ConversationStore {
  const conversation = createConversation(agentId, now);
  return { activeId: conversation.id, items: [conversation] };
}

/** First user message, trimmed to a sidebar-sized label. */
export function titleFromMessages(messages: Message[]): string {
  const first = messages.find((m) => m.role === 'user' && m.content.trim());
  if (!first) return DEFAULT_TITLE;
  const text = first.content.trim().replace(/\s+/g, ' ');
  return text.length > MAX_TITLE_CHARS
    ? `${text.slice(0, MAX_TITLE_CHARS - 1).trimEnd()}\u2026`
    : text;
}

export function activeConversation(store: ConversationStore): Conversation | undefined {
  return store.items.find((c) => c.id === store.activeId);
}

/**
 * Write messages into a conversation. The title follows the first user message
 * until the user renames it — an explicit rename is never overwritten.
 */
export function withMessages(
  store: ConversationStore,
  id: string,
  messages: Message[],
  now: number = Date.now()
): ConversationStore {
  return {
    ...store,
    items: store.items.map((c) =>
      c.id === id
        ? {
            ...c,
            messages,
            updatedAt: now,
            title: c.renamed ? c.title : titleFromMessages(messages),
          }
        : c
    ),
  };
}

export function addConversation(
  store: ConversationStore,
  conversation: Conversation
): ConversationStore {
  return { activeId: conversation.id, items: [...store.items, conversation] };
}

export function renameConversation(
  store: ConversationStore,
  id: string,
  title: string,
  now: number = Date.now()
): ConversationStore {
  const clean = title.trim().slice(0, MAX_TITLE_CHARS);
  if (!clean) return store;
  return {
    ...store,
    items: store.items.map((c) =>
      c.id === id ? { ...c, title: clean, renamed: true, updatedAt: now } : c
    ),
  };
}

export function deleteConversation(store: ConversationStore, id: string): ConversationStore {
  const items = store.items.filter((c) => c.id !== id);
  if (items.length === 0) {
    const replacement = createConversation(null);
    return { activeId: replacement.id, items: [replacement] };
  }
  if (store.activeId !== id) return { ...store, items };
  // Deleted the active one: fall back to the most recently updated thread.
  const next = [...items].sort((a, b) => b.updatedAt - a.updatedAt)[0];
  return { activeId: next.id, items };
}

/** Clear the messages of one conversation, keeping its agent and id. */
export function clearConversation(
  store: ConversationStore,
  id: string,
  now: number = Date.now()
): ConversationStore {
  return {
    ...store,
    items: store.items.map((c) =>
      c.id === id
        ? { ...c, messages: [], title: DEFAULT_TITLE, renamed: false, updatedAt: now }
        : c
    ),
  };
}

/** Newest first — the order the conversation switcher renders. */
export function sortedConversations(store: ConversationStore): Conversation[] {
  return [...store.items].sort((a, b) => b.updatedAt - a.updatedAt);
}

/** Drop empty conversations, but never the one the user is looking at. */
export function pruneEmpty(store: ConversationStore): ConversationStore {
  const items = store.items.filter((c) => c.id === store.activeId || c.messages.length > 0);
  return items.length === store.items.length ? store : { ...store, items };
}

function coerceMessages(value: unknown): Message[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (m): m is Message =>
      m !== null &&
      typeof m === 'object' &&
      ((m as Message).role === 'user' || (m as Message).role === 'assistant') &&
      typeof (m as Message).content === 'string'
  );
}

/** Parse a stored blob, repairing anything malformed into a usable store. */
export function parseStore(raw: unknown): ConversationStore {
  if (typeof raw !== 'string' || !raw.trim()) return createStore();
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return createStore();
  }
  if (!data || typeof data !== 'object') return createStore();

  const record = data as { activeId?: unknown; items?: unknown };
  const items = (Array.isArray(record.items) ? record.items : [])
    .filter((c): c is Record<string, unknown> => !!c && typeof c === 'object')
    .map((c, i) => ({
      id: typeof c.id === 'string' && c.id ? c.id : `conv-recovered-${i}`,
      title: typeof c.title === 'string' && c.title ? c.title : DEFAULT_TITLE,
      agentId: typeof c.agentId === 'string' && c.agentId ? c.agentId : null,
      messages: coerceMessages(c.messages),
      updatedAt: typeof c.updatedAt === 'number' ? c.updatedAt : 0,
    }));

  if (items.length === 0) return createStore();

  const activeId =
    typeof record.activeId === 'string' && items.some((c) => c.id === record.activeId)
      ? record.activeId
      : [...items].sort((a, b) => b.updatedAt - a.updatedAt)[0].id;

  return pruneEmpty({ activeId, items });
}

export function serializeStore(store: ConversationStore): string {
  return JSON.stringify(store);
}

/**
 * Reject a stored agent id that no longer exists (deleted agent) so the chat
 * doesn't post replies as a persona the user can no longer see or edit.
 */
export function reconcileAgents(
  store: ConversationStore,
  agentIds: string[]
): ConversationStore {
  const known = new Set(agentIds);
  let changed = false;
  const items = store.items.map((c) => {
    if (c.agentId && !known.has(c.agentId)) {
      changed = true;
      return { ...c, agentId: null };
    }
    return c;
  });
  return changed ? { ...store, items } : store;
}
