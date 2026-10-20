// Retention + storage-selection rules for chat persistence, driven by the
// data_controls settings. Pure functions — node-testable without React/DOM.

export const RETENTION_MS: Record<string, number> = {
  '1_day': 24 * 60 * 60 * 1000,
  '7_days': 7 * 24 * 60 * 60 * 1000,
  '30_days': 30 * 24 * 60 * 60 * 1000,
  '90_days': 90 * 24 * 60 * 60 * 1000,
};

/**
 * Drop messages older than the retention window. Messages without `ts` are
 * legacy — kept, never nuke existing data. session_only/indefinite keep all
 * (session_only is enforced by the storage backend instead).
 */
export function filterByRetention<T extends { ts?: number }>(
  msgs: T[],
  retention: unknown
): T[] {
  const ms = RETENTION_MS[String(retention ?? '')];
  if (!ms) return msgs;
  const cutoff = Date.now() - ms;
  return msgs.filter((m) => typeof m.ts !== 'number' || m.ts >= cutoff);
}

/** save_chat_history=false → memory-only chat. */
export function isHistoryEnabled(dataControls: Record<string, unknown> | undefined): boolean {
  return dataControls?.save_chat_history !== false;
}

/**
 * clear_on_exit (and session_only retention) → sessionStorage: data dies with
 * the tab natively, no unload-event hacks.
 */
export function isSessionOnly(dataControls: Record<string, unknown> | undefined): boolean {
  return (
    dataControls?.clear_on_exit === true ||
    dataControls?.data_retention === 'session_only'
  );
}

/**
 * Parental max_session_duration_minutes: 0 = unlimited, else the epoch-ms
 * deadline. An expired deadline means "session over" — new sends rejected.
 */
export function sessionDeadlineMinutes(parental: Record<string, unknown> | undefined): number {
  const v = Number(parental?.max_session_duration_minutes ?? 0);
  return Number.isFinite(v) && v > 0 ? v : 0;
}

export function isSessionExpired(
  parental: Record<string, unknown> | undefined,
  sessionStart: number
): boolean {
  const mins = sessionDeadlineMinutes(parental);
  return mins > 0 && Date.now() - sessionStart > mins * 60 * 1000;
}
