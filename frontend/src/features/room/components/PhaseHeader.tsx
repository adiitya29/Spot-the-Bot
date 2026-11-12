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
    <header className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/95 p-4 shadow-lg">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-slate-800 px-2.5 py-1 font-mono text-[11px] font-semibold tracking-wider text-slate-300">
            ROOM {code}
          </span>
          <span className="rounded-full bg-teal-500/15 px-2.5 py-1 text-xs font-semibold text-teal-300">
            Round {roundNumber} of {totalRounds}
          </span>
        </div>
        <div
          aria-live="polite"
          aria-label="Time remaining"
          className={`rounded-xl border px-3 py-1 font-mono text-base font-bold tabular-nums ${
            isUrgent
              ? "border-rose-500/40 bg-rose-500/15 text-rose-300"
              : "border-slate-700 bg-slate-950 text-white"
          }`}
        >
          {formatCountdown(remainingSeconds)}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-slate-200">
          Phase: {PHASE_LABELS[phase] ?? phase}
        </span>

        {mySeat && theme ? (
          <div
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${theme.badge} ${theme.text}`}
          >
            <span aria-hidden="true" className={`h-2 w-2 rounded-full ${theme.dot}`} />
            <span>You are {mySeat.alias}</span>
          </div>
        ) : null}
      </div>
    </header>
  );
}

