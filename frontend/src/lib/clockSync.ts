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
