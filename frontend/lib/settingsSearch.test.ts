import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { searchSettings, SETTINGS_FIELDS } from './settingsSearch.ts';

test('searchSettings returns nothing for an empty/blank query', () => {
  assert.deepEqual(searchSettings(''), []);
  assert.deepEqual(searchSettings('   '), []);
});

test('searchSettings matches labels case-insensitively', () => {
  const out = searchSettings('TEMPERATURE');
  assert.ok(out.some((f) => f.label === 'Temperature' && f.section === 'general'));
});

test('searchSettings matches keywords/aliases', () => {
  assert.ok(searchSettings('nsfw').some((f) => f.label === 'Block explicit content'));
  assert.ok(searchSettings('tray').some((f) => f.label === 'Minimize to tray'));
  assert.ok(searchSettings('tok/s').some((f) => f.label === 'Show token speed'));
});

test('searchSettings ranks label-prefix matches first', () => {
  const out = searchSettings('max');
  assert.equal(out[0].label, 'Max Tokens');
  assert.ok(out.length >= 3);
});

test('searchSettings returns [] when nothing matches', () => {
  assert.deepEqual(searchSettings('zzzzz'), []);
});

test('every indexed field label still exists in its section component', () => {
  const files: Record<string, string> = {
    general: 'GeneralSettings.tsx',
    project: 'ProjectSettings.tsx',
    personalization: 'PersonalizationSettings.tsx',
    data_controls: 'DataControlsSettings.tsx',
    security: 'SecuritySettings.tsx',
    parental_controls: 'ParentalControlsSettings.tsx',
  };
  const cache: Record<string, string> = {};
  for (const field of SETTINGS_FIELDS) {
    const file = files[field.section];
    assert.ok(file, `unknown section in catalog: ${field.section}`);
    cache[file] ??= readFileSync(
      fileURLToPath(new URL(`../components/settings/${file}`, import.meta.url)),
      'utf8'
    );
    assert.ok(
      cache[file].includes(field.label),
      `label "${field.label}" (${field.section}) no longer appears in ${file} — update settingsSearch.ts`
    );
  }
});
