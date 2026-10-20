// Pure helpers for masked-LM ([MASK] prediction) results.
// NOTE: keep this module free of `@/` path aliases — Node's native TS test
// runner cannot resolve them.

export interface Candidate {
  token: string;
  probability: number; // fraction in [0, 1], e.g. 0.415
}

export interface MaskPrediction {
  position: number;
  candidates: Candidate[];
}

export interface Segment {
  text: string;
  filled: boolean; // true when this is a substituted [MASK] position
}

// BERT subword pieces carry a '##' prefix — strip it for display.
export function cleanToken(token: string): string {
  return token.replace(/^##+/, '');
}

// Build the fill-in-the-blank preview: replace each [MASK] in order with the
// top candidate. Backend predictions are ordered by ascending token position,
// which matches left-to-right [MASK] order in the input text.
export function buildSegments(input: string, predictions: MaskPrediction[]): Segment[] {
  const parts = input.split('[MASK]');
  const segments: Segment[] = [];
  parts.forEach((part, idx) => {
    if (part) segments.push({ text: part, filled: false });
    if (idx < parts.length - 1) {
      const pred = predictions[idx];
      const token =
        pred && pred.candidates[0] ? cleanToken(pred.candidates[0].token) : '[MASK]';
      segments.push({ text: token, filled: true });
    }
  });
  return segments;
}
