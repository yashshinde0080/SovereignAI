import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildSegments, cleanToken } from './maskedLm.ts';
import type { MaskPrediction } from './maskedLm.ts';

const single = (position: number, token: string, probability: number): MaskPrediction => ({
  position,
  candidates: [{ token, probability }],
});

test('cleanToken strips BERT ## subword prefix', () => {
  assert.equal(cleanToken('##oma'), 'oma');
  assert.equal(cleanToken('lung'), 'lung');
  assert.equal(cleanToken('###multi'), 'multi');
});

test('buildSegments substitutes top candidate into [MASK] in order', () => {
  const segments = buildSegments('The patient was diagnosed with [MASK] cancer.', [
    {
      position: 6,
      candidates: [
        { token: 'lung', probability: 0.415 },
        { token: 'breast', probability: 0.309 },
      ],
    },
  ]);
  assert.deepEqual(segments, [
    { text: 'The patient was diagnosed with ', filled: false },
    { text: 'lung', filled: true },
    { text: ' cancer.', filled: false },
  ]);
});

test('buildSegments handles multiple masks with per-position candidates', () => {
  const segments = buildSegments('[MASK] is the most common [MASK].', [
    {
      position: 0,
      candidates: [
        { token: 'lung', probability: 0.4 },
        { token: 'skin', probability: 0.3 },
      ],
    },
    {
      position: 5,
      candidates: [
        { token: 'cancer', probability: 0.8 },
        { token: 'tumor', probability: 0.1 },
      ],
    },
  ]);
  const filled = segments.filter((s) => s.filled).map((s) => s.text);
  assert.deepEqual(filled, ['lung', 'cancer']);
});

test('buildSegments falls back to [MASK] when a prediction is missing', () => {
  const segments = buildSegments('[MASK] and [MASK]', [single(0, 'only', 1.0)]);
  const filled = segments.filter((s) => s.filled).map((s) => s.text);
  assert.deepEqual(filled, ['only', '[MASK]']);
});

test('buildSegments cleans ## subword prefix from candidate', () => {
  const segments = buildSegments('I have [MASK]', [single(2, '##oma', 0.6)]);
  assert.equal(segments.filter((s) => s.filled)[0].text, 'oma');
});

test('buildSegments keeps [MASK] when a position has no candidates', () => {
  const segments = buildSegments('hello [MASK]', [{ position: 1, candidates: [] }]);
  assert.equal(segments.filter((s) => s.filled)[0].text, '[MASK]');
});
