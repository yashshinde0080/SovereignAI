// encrypt_local_data — AES-GCM at rest for chat history in localStorage.
// Key lives in localStorage too (sovereign.chat.key) — this is at-rest
// obfuscation against casual file/copy snooping, NOT protection against
// code running in the same origin. Say so in the settings description.
// ponytail: WebCrypto only, no deps; swap key storage to password-derived
// PBKDF2 if real at-rest secrecy is ever needed.

const KEY_STORAGE = 'sovereign.chat.key';
const PREFIX = 'enc:v1:'; // versioned payload marker (base64 iv + ct)

async function getKey(): Promise<CryptoKey> {
  let raw = window.localStorage.getItem(KEY_STORAGE);
  if (!raw) {
    const bytes = new Uint8Array(32);
    crypto.getRandomValues(bytes);
    raw = btoa(String.fromCharCode(...bytes));
    window.localStorage.setItem(KEY_STORAGE, raw);
  }
  const bytes = Uint8Array.from(atob(raw), (c) => c.charCodeAt(0));
  return crypto.subtle.importKey('raw', bytes, 'AES-GCM', false, ['encrypt', 'decrypt']);
}

function toB64(buf: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buf)));
}

function fromB64(s: string): Uint8Array<ArrayBuffer> {
  const buf = new ArrayBuffer(s.length);
  const arr = new Uint8Array(buf);
  for (let i = 0; i < s.length; i++) arr[i] = s.charCodeAt(i);
  return arr;
}

export function isEncrypted(text: string): boolean {
  return typeof text === 'string' && text.startsWith(PREFIX);
}

export async function encryptText(plaintext: string): Promise<string> {
  const iv = new Uint8Array(12);
  crypto.getRandomValues(iv);
  const key = await getKey();
  const ct = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    new TextEncoder().encode(plaintext)
  );
  return PREFIX + toB64(iv.buffer as ArrayBuffer) + ':' + toB64(ct);
}

export async function decryptText(payload: string): Promise<string> {
  const body = payload.slice(PREFIX.length);
  const [ivB64, ctB64] = body.split(':');
  if (!ivB64 || !ctB64) throw new Error('bad ciphertext');
  const key = await getKey();
  const pt = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: fromB64(ivB64) },
    key,
    fromB64(ctB64)
  );
  return new TextDecoder().decode(pt);
}
