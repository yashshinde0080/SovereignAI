'use client';

import { useState } from 'react';
import { Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { API_BASE } from '@/lib/apiBase';

/**
 * Full-app lock screen (security.require_password) and settings PIN prompt
 * (parental_controls.require_pin_for_settings). Verification happens against
 * the backend (bcrypt hashes live there) — the frontend only remembers that
 * this tab is unlocked, in sessionStorage.
 */
export function LockScreen({ onUnlock }: { onUnlock: () => void }) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const submit = async () => {
    if (!value.trim() || checking) return;
    setChecking(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/v1/settings/security/verify-password?password=${encodeURIComponent(value)}`, {
        method: 'POST',
      });
      const data = await res.json().catch(() => ({ valid: false }));
      if (data.valid) {
        window.sessionStorage.setItem('sovereign.unlocked', '1');
        onUnlock();
      } else {
        setError('Wrong password');
        setValue('');
      }
    } catch {
      setError('Backend unreachable — cannot verify');
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950">
      <div className="w-full max-w-xs space-y-4 text-center">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
          <Lock className="h-6 w-6 text-primary" />
        </div>
        <h1 className="text-lg font-semibold">SovereignAI is locked</h1>
        <p className="text-sm text-muted-foreground">
          Enter the app password to continue.
        </p>
        <Input
          type="password"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="App password"
          disabled={checking}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button className="w-full" onClick={submit} disabled={checking || !value.trim()}>
          {checking ? 'Checking…' : 'Unlock'}
        </Button>
      </div>
    </div>
  );
}

export function PinPrompt({ onUnlock, onCancel }: { onUnlock: () => void; onCancel: () => void }) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const submit = async () => {
    if (!value.trim() || checking) return;
    setChecking(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/v1/settings/parental-controls/verify-pin?pin=${encodeURIComponent(value)}`, {
        method: 'POST',
      });
      const data = await res.json().catch(() => ({ valid: false }));
      if (data.valid) {
        window.sessionStorage.setItem('sovereign.pin_ok', '1');
        onUnlock();
      } else {
        setError('Wrong PIN');
        setValue('');
      }
    } catch {
      setError('Backend unreachable — cannot verify');
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/95">
      <div className="w-full max-w-xs space-y-4 text-center">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
          <Lock className="h-6 w-6 text-primary" />
        </div>
        <h1 className="text-lg font-semibold">Settings locked</h1>
        <p className="text-sm text-muted-foreground">Enter the parental PIN to open Settings.</p>
        <Input
          type="password"
          inputMode="numeric"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="PIN"
          disabled={checking}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex gap-2">
          <Button variant="ghost" className="flex-1" onClick={onCancel}>
            Cancel
          </Button>
          <Button className="flex-1" onClick={submit} disabled={checking || !value.trim()}>
            {checking ? 'Checking…' : 'Unlock'}
          </Button>
        </div>
      </div>
    </div>
  );
}
