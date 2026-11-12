/**
 * Compute clock offset between server UTC epoch ms and local Date.now().
 * Countdown remaining = endsAtMs - (Date.now() + offsetMs).
 */
export function computeClockOffset(serverTimeMs: number, localNowMs: number = Date.now()): number {
  return serverTimeMs - localNowMs;
}

export function getRemainingSeconds(
  endsAtMs: number,
  offsetMs: number,
  localNowMs: number = Date.now(),
): number {
  const remainingMs = endsAtMs - (localNowMs + offsetMs);
  return Math.max(0, Math.ceil(remainingMs / 1000));
}

export function formatCountdown(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));
  const mins = Math.floor(safeSeconds / 60);
  const secs = safeSeconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}
