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
      className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-xl backdrop-blur-xl sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 pb-4">
        <div>
          <h2 className="text-lg font-black tracking-tight text-white sm:text-xl">
            Who is the AI Bot?
          </h2>
          <p className="mt-0.5 text-xs text-slate-400">
            {hasVoted
              ? "Vote locked in. Waiting for everyone else..."
              : "Pick the suspect seat and lock in your vote (+100 pts if right)."}
          </p>
        </div>
        <span className="rounded-lg border border-white/10 bg-black/40 px-3 py-1 font-mono text-xs font-bold text-slate-300">
          {votesCast}/{totalHumans || seats.length - 1} voted
        </span>
      </div>

      {hasVoted && lockedCandidate ? (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/15 px-4 py-3 text-xs font-bold text-emerald-200 shadow-sm">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>You voted for {lockedCandidate.alias}</span>
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
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
              className={`flex flex-col justify-between rounded-xl border p-4 text-left transition-all disabled:cursor-not-allowed ${
                isSelected
                  ? "border-teal-400 bg-teal-500/15 shadow-lg shadow-teal-500/10 ring-2 ring-teal-400/50"
                  : "border-white/10 bg-black/40 hover:border-white/20 hover:bg-white/5"
              }`}
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs font-bold">
                    <span
                      aria-hidden="true"
                      className={`h-2.5 w-2.5 rounded-full ring-2 ring-white/10 ${theme.dot}`}
                    />
                    <span className={theme.text}>{seat.alias}</span>
                  </div>
                  {isSelected ? (
                    <span className="rounded-md bg-teal-400/20 px-2 py-0.5 text-[10px] font-extrabold tracking-wider text-teal-300 uppercase">
                      {hasVoted ? "Voted" : "Selected"}
                    </span>
                  ) : null}
                </div>
                {answerText ? (
                  <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-slate-300 italic">
                    “{answerText}”
                  </p>
                ) : null}
              </div>
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
          className="min-h-12 w-full rounded-xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 px-5 text-sm font-bold text-slate-950 shadow-lg shadow-teal-500/25 transition-all hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100 disabled:active:scale-100"
        >
          Lock In Vote
        </button>
      ) : null}
    </section>
  );
}
