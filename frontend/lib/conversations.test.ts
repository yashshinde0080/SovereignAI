import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  createConversation,
  createStore,
  addConversation,
  activeConversation,
  clearConversation,
  deleteConversation,
  parseStore,
  pruneEmpty,
  reconcileAgents,
  renameConversation,
  serializeStore,
  sortedConversations,
  titleFromMessages,
  withMessages,
  DEFAULT_TITLE,
  MAX_TITLE_CHARS,
} from './conversations.ts';
import type { Message } from '../types/index.ts';

const msg = (role: Message['role'], content: string): Message => ({ role, content });

test('titleFromMessages uses the first user message', () => {
  const messages = [msg('user', '  What should we prioritize in our next release?  ')];
  assert.equal(titleFromMessages(messages), 'What should we prioritize in our next release?');
});

test('titleFromMessages ignores assistant-only threads and truncates long ones', () => {
  assert.equal(titleFromMessages([msg('assistant', 'hi')]), DEFAULT_TITLE);
  assert.equal(titleFromMessages([]), DEFAULT_TITLE);

  const long = 'x'.repeat(200);
  const title = titleFromMessages([msg('user', long)]);
  assert.equal(title.length, MAX_TITLE_CHARS);
  assert.ok(title.endsWith('\u2026'));
});

test('withMessages updates content and auto title, but not a renamed thread', () => {
  const started = createStore('agent_ceo');
  const id = started.activeId;
  const typed = withMessages(started, id, [msg('user', 'hello there')]);
  assert.equal(activeConversation(typed)!.title, 'hello there');

  const renamed = renameConversation(typed, id, 'Board prep');
  assert.equal(activeConversation(renamed)!.title, 'Board prep');

  const later = withMessages(renamed, id, [msg('user', 'hello there'), msg('user', 'follow up')]);
  assert.equal(activeConversation(later)!.title, 'Board prep', 'rename must survive new messages');
});

test('withMessages leaves other conversations untouched', () => {
  let store = createStore('agent_ceo');
  const ceo = store.activeId;
  const cto = createConversation('agent_cto');
  store = addConversation(store, cto);

  store = withMessages(store, ceo, [msg('user', 'ceo question')]);
  assert.equal(store.items.find((c) => c.id === ceo)!.messages.length, 1);
  assert.equal(store.items.find((c) => c.id === cto.id)!.messages.length, 0);
  assert.equal(store.items.find((c) => c.id === cto.id)!.agentId, 'agent_cto');
});

test('addConversation makes the new conversation active', () => {
  const store = createStore('agent_ceo');
  const next = addConversation(store, createConversation('agent_cto'));
  assert.equal(next.activeId, next.items[1].id);
  assert.equal(activeConversation(next)!.agentId, 'agent_cto');
});

test('deleteConversation falls back to the newest remaining thread', () => {
  let store = createStore('agent_ceo');
  const first = store.activeId;
  const second = createConversation('agent_cto', 1000);
  store = addConversation(store, second);
  store = withMessages(store, first, [msg('user', 'old')], 1);
  store = withMessages(store, second.id, [msg('user', 'new')], 2000);

  const after = deleteConversation(store, second.id);
  assert.equal(after.activeId, first);
  assert.equal(after.items.length, 1);

  // Deleting a non-active thread keeps the active one.
  const third = createConversation(null, 3000);
  const withThird = addConversation(after, third);
  const pruned = deleteConversation(withThird, first);
  assert.equal(pruned.activeId, third.id);
});

test('deleting the last conversation leaves an empty replacement', () => {
  const store = createStore('agent_ceo');
  const after = deleteConversation(store, store.activeId);
  assert.equal(after.items.length, 1);
  assert.equal(after.items[0].messages.length, 0);
  assert.equal(after.activeId, after.items[0].id);
});

test('clearConversation keeps the agent and id but drops messages and title', () => {
  let store = createStore('agent_cto');
  const id = store.activeId;
  store = withMessages(store, id, [msg('user', 'hi')]);
  store = renameConversation(store, id, 'Mine');

  const cleared = clearConversation(store, id);
  const conv = activeConversation(cleared)!;
  assert.equal(conv.id, id);
  assert.equal(conv.agentId, 'agent_cto');
  assert.deepEqual(conv.messages, []);
  assert.equal(conv.title, DEFAULT_TITLE);
});

test('parseStore round-trips a serializeStore blob', () => {
  let store = createStore('agent_ceo');
  store = withMessages(store, store.activeId, [msg('user', 'hi'), msg('assistant', 'ok')]);
  const restored = parseStore(serializeStore(store));
  assert.equal(restored.activeId, store.activeId);
  assert.equal(restored.items[0].messages.length, 2);
  assert.equal(restored.items[0].agentId, 'agent_ceo');
});

test('parseStore repairs junk instead of throwing', () => {
  for (const junk of ['', '   ', 'not json', '[]', 'null', '{"items": "nope"}', 42]) {
    const store = parseStore(junk as unknown);
    assert.equal(store.items.length, 1);
    assert.equal(store.activeId, store.items[0].id);
  }

  // An unknown active id falls back to the newest thread, and a malformed
  // messages value is repaired to an empty thread rather than throwing.
  const repaired = parseStore(
    JSON.stringify({
      activeId: 'missing',
      items: [
        { id: 'a', messages: [{ role: 'user', content: 'hi' }], updatedAt: 5 },
        { id: 'b', messages: 'nope', updatedAt: 9 },
      ],
    })
  );
  assert.equal(repaired.activeId, 'b');
  assert.deepEqual(repaired.items.find((c) => c.id === 'b')!.messages, []);
  assert.equal(repaired.items.find((c) => c.id === 'a')!.messages.length, 1);
});

test('pruneEmpty drops empty threads but keeps the active one', () => {
  let store = createStore('agent_ceo');
  const first = store.activeId;
  store = addConversation(store, createConversation('agent_cto', 999));
  const active = store.activeId; // the new, still-empty, active thread

  const pruned = pruneEmpty(store);
  assert.equal(pruned.items.length, 1);
  assert.equal(pruned.items[0].id, active);
  assert.ok(!pruned.items.some((c) => c.id === first));
});

test('reconcileAgents clears an agent that no longer exists', () => {
  let store = createStore('agent_deleted');
  store = withMessages(store, store.activeId, [msg('user', 'hi')]);
  const fixed = reconcileAgents(store, ['agent_ceo']);
  assert.equal(activeConversation(fixed)!.agentId, null);

  const kept = reconcileAgents(store, ['agent_deleted']);
  assert.equal(activeConversation(kept)!.agentId, 'agent_deleted');
});

test('sortedConversations returns newest first', () => {
  let store = createStore('agent_ceo');
  const a = store.activeId;
  const b = createConversation('agent_cto', 10);
  store = addConversation(store, b);
  store = withMessages(store, a, [msg('user', 'x')], 5000);
  assert.deepEqual(
    sortedConversations(store).map((c) => c.id),
    [a, b.id]
  );
});

test('conversation ids are unique', () => {
  const ids = new Set(Array.from({ length: 200 }, () => createConversation(null).id));
  assert.equal(ids.size, 200);
});
