import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { twMerge } from 'tailwind-merge';

// components/ui/dialog.tsx defaults to `sm:max-w-lg` (512px). A caller that passes only
// `max-w-[900px]` does NOT beat it — Tailwind v4 emits arbitrary max-w values before the
// named scale, so the 512px rule wins the cascade and the dialog silently clips its content.
// Any dialog that sets its own width must set the `sm:` variant too, so tailwind-merge
// drops the default instead of leaving both rules to fight it out.
const BASE = 'fixed w-full max-w-[calc(100%-2rem)] sm:max-w-lg';
const here = dirname(fileURLToPath(import.meta.url));
const callSites: [string, string][] = [
  ['../components/settings/SettingsDialog.tsx', 'max-w-[900px]'],
  ['../components/settings/AgentSettings.tsx', 'max-w-[min(680px,95vw)]'],
];

for (const [rel, width] of callSites) {
  test(`${rel} is not capped at 512px by the dialog default`, () => {
    const src = readFileSync(join(here, rel), 'utf8');
    const found = src.match(/<DialogContent className="([^"]+)"/);
    assert.ok(found, 'no <DialogContent className=... to check');
    assert.ok(found[1].includes(width), `expected caller width ${width} in the class list`);
    const merged = twMerge(`${BASE} ${found[1]}`);
    assert.ok(!merged.includes('sm:max-w-lg'), 'sm:max-w-lg survived the merge -> dialog renders 512px wide');
  });
}
