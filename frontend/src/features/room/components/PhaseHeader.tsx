import { useEffect, useState } from "react";
import { formatCountdown, getRemainingSeconds } from "../../../lib/clockSync";
import { getSeatColorTheme } from "../../../lib/constants";
import type { RoundSeat } from "../types";

interface PhaseHeaderProps {
  code: string;
  phase: string;
  roundNumber: number;
  totalRounds: number;
  phaseEndsAtMs: number | null;
  clockOffsetMs: number;
  mySeat: RoundSeat | null;
}

const PHASE_LABELS: Record<string, string> = {
  answer: "Answer",
  chat: "Group Chat",
  vote: "Vote",
  reveal: "Reveal",
  done: "Round Complete",
};

export function PhaseHeader({
  code,
  phase,
  roundNumber,
  totalRounds,
  phaseEndsAtMs,
  clockOffsetMs,
  mySeat,
}: PhaseHeaderProps) {
  const [remainingSeconds, setRemainingSeconds] = useState<number>(() =>
    phaseEndsAtMs === null ? 0 : getRemainingSeconds(phaseEndsAtMs, clockOffsetMs),
  );

  useEffect(() => {
    if (phaseEndsAtMs === null) {
      setRemainingSeconds(0);
      return;
    }
    const update = () => {
      setRemainingSeconds(getRemainingSeconds(phaseEndsAtMs, clockOffsetMs));
    };
    update();
    const timer = window.setInterval(update, 250);
    return () => window.clearInterval(timer);
  }, [phaseEndsAtMs, clockOffsetMs]);

  const theme = mySeat ? getSeatColorTheme(mySeat.color_index) : null;
  const isUrgent = remainingSeconds > 0 && remainingSeconds <= 10;

  return (
    <header className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 shadow-xl backdrop-blur-xl sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="rounded-lg border border-white/10 bg-black/40 px-3 py-1 font-mono text-xs font-bold tracking-widest text-slate-300">
            ROOM {code}
          </span>
          <span className="rounded-lg border border-teal-500/20 bg-teal-500/10 px-3 py-1 font-mono text-xs font-semibold text-teal-300">
            Round {roundNumber} of {totalRounds}
          </span>
        </div>
        <div
          aria-live="polite"
          aria-label="Time remaining"
          className={`flex items-center gap-1.5 rounded-xl border px-3.5 py-1.5 font-mono text-base font-bold tabular-nums shadow-inner transition-all ${
            isUrgent
              ? "border-rose-500/50 bg-rose-500/20 text-rose-300 animate-pulse ring-2 ring-rose-500/30"
              : "border-white/10 bg-black/50 text-white"
          }`}
        >
          <span className="text-xs opacity-60">⏱</span>
          <span>{formatCountdown(remainingSeconds)}</span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-white/5 pt-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
          <span className="text-xs uppercase tracking-wider text-slate-400">Phase:</span>
          <span className="text-white font-bold">{PHASE_LABELS[phase] ?? phase}</span>
        </div>

        {mySeat && theme ? (
          <div
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold shadow-sm ${theme.badge} ${theme.text}`}
          >
            <span
              aria-hidden="true"
              className={`h-2 w-2 rounded-full ring-2 ring-white/20 ${theme.dot}`}
            />
            <span>You are {mySeat.alias}</span>
          </div>
        ) : null}
      </div>
    </header>
  );
}
