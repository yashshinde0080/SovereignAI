import { test } from 'node:test';
import assert from 'node:assert/strict';
import { filterByRetention, isHistoryEnabled, isSessionOnly, RETENTION_MS } from './chatRetention.ts';

test('filterByRetention drops messages older than the window', () => {
  const now = Date.now();
  const msgs = [
    { ts: now - 2 * RETENTION_MS['1_day'] }, // stale
    { ts: now - 60 * 1000 },                 // fresh
  ];
  const out = filterByRetention(msgs, '1_day');
  assert.equal(out.length, 1);
  assert.equal(out[0].ts, msgs[1].ts);
});

test('filterByRetention keeps messages with no ts (legacy data never nuked)', () => {
  const msgs = [{}, { ts: Date.now() - 60 * 1000 }];
  const out = filterByRetention(msgs, '7_days');
  assert.equal(out.length, 2); // no-ts legacy + fresh both survive
  assert.deepEqual(filterByRetention([{}], '1_day'), [{}]);
});

test('filterByRetention keeps everything for session_only/indefinite/unknown', () => {
  const stale = [{ ts: 0 }];
  for (const policy of ['session_only', 'indefinite', 'bogus', undefined, null]) {
    assert.equal(filterByRetention(stale, policy).length, 1, String(policy));
  }
});

test('isHistoryEnabled: off only when save_chat_history is exactly false', () => {
  assert.equal(isHistoryEnabled({ save_chat_history: false }), false);
  assert.equal(isHistoryEnabled({ save_chat_history: true }), true);
  assert.equal(isHistoryEnabled({}), true);       // default on
  assert.equal(isHistoryEnabled(undefined), true); // settings missing → default on
});

test('isSessionOnly: clear_on_exit or session_only retention', () => {
  assert.equal(isSessionOnly({ clear_on_exit: true }), true);
  assert.equal(isSessionOnly({ data_retention: 'session_only' }), true);
  assert.equal(isSessionOnly({ clear_on_exit: false, data_retention: '30_days' }), false);
  assert.equal(isSessionOnly(undefined), false);
});
