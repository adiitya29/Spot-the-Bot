import { useState } from "react";
import { getSeatColorTheme } from "../../../lib/constants";
import type { RoundAnswer, RoundSeat } from "../types";

interface VotePanelProps {
  seats: RoundSeat[];
  mySeatId: string | null;
  answers: RoundAnswer[];
  votesCast: number;
  totalHumans: number;
  myVoteTargetSeatId: string | null;
  disabled: boolean;
  onCastVote: (targetSeatId: string) => void;
}

export function VotePanel({
  seats,
  mySeatId,
  answers,
  votesCast,
  totalHumans,
  myVoteTargetSeatId,
  disabled,
  onCastVote,
}: VotePanelProps) {
  const [selectedSeatId, setSelectedSeatId] = useState<string | null>(null);
  const effectiveTarget = myVoteTargetSeatId ?? selectedSeatId;
  const answerBySeatId = new Map(answers.map((ans) => [ans.seat_id, ans.text]));
  const candidates = seats.filter((seat) => seat.seat_id !== mySeatId);
  const hasVoted = myVoteTargetSeatId !== null;
  const lockedCandidate = seats.find((seat) => seat.seat_id === myVoteTargetSeatId) ?? null;

  return (
    <section
      aria-label="Vote for the bot"
      className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/95 p-5 shadow-lg"
    >
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-bold text-white">Who is the AI Bot?</h2>
          <p className="text-xs text-slate-400">
            {hasVoted
              ? "Vote locked in. Waiting for everyone else..."
              : "Pick the suspect seat and lock in your vote (+100 pts if right)."}
          </p>
        </div>
        <span className="rounded-full bg-slate-800 px-3 py-1 font-mono text-xs font-semibold text-slate-200">
          {votesCast}/{totalHumans || seats.length - 1} voted
        </span>
      </div>

      {hasVoted && lockedCandidate ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-2.5 text-xs font-semibold text-emerald-200">
          You voted for {lockedCandidate.alias}
        </div>
      ) : null}

      <div className="grid gap-2 sm:grid-cols-2">
        {candidates.map((seat) => {
          const theme = getSeatColorTheme(seat.color_index);
          const isSelected = effectiveTarget === seat.seat_id;
          const answerText = answerBySeatId.get(seat.seat_id);
          return (
            <button
              key={seat.seat_id}
              type="button"
              disabled={hasVoted || disabled}
              aria-pressed={isSelected}
              onClick={() => setSelectedSeatId(seat.seat_id)}
              className={`min-h-14 rounded-xl border p-3 text-left transition disabled:cursor-not-allowed ${
                isSelected
                  ? "border-teal-400 bg-teal-500/15 ring-1 ring-teal-400"
                  : "border-slate-800 bg-slate-950/70 hover:border-slate-700"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs font-semibold">
                  <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${theme.dot}`} />
                  <span className={theme.text}>{seat.alias}</span>
                </div>
                {isSelected ? (
                  <span className="text-[10px] font-bold tracking-wide text-teal-300 uppercase">
                    {hasVoted ? "Voted" : "Selected"}
                  </span>
                ) : null}
              </div>
              {answerText ? (
                <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-slate-300">
                  “{answerText}”
                </p>
              ) : null}
            </button>
          );
        })}
      </div>

      {!hasVoted ? (
        <button
          type="button"
          disabled={!selectedSeatId || disabled}
          onClick={() => {
            if (selectedSeatId) {
              onCastVote(selectedSeatId);
            }
          }}
          className="min-h-11 w-full rounded-xl bg-teal-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Lock In Vote
        </button>
      ) : null}
    </section>
  );
}
