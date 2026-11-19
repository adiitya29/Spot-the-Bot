import type { LeaderboardEntry, RoundSummaryEntry } from "../types";
import { ShareCard } from "./ShareCard";

interface LeaderboardProps {
  entries: LeaderboardEntry[];
  myPlayerId: string | null;
  roundsSummary?: RoundSummaryEntry[];
  botFooledCount?: number;
  totalRounds?: number;
  isGameOver?: boolean;
  isHost?: boolean;
  disabled?: boolean;
  roomCode?: string;
  onPlayAgain?: () => void;
}

export function Leaderboard({
  entries,
  myPlayerId,
  roundsSummary,
  botFooledCount = 0,
  totalRounds = 3,
  isGameOver = false,
  isHost = false,
  disabled = false,
  roomCode,
  onPlayAgain,
}: LeaderboardProps) {
  return (
    <section
      aria-label={isGameOver ? "Final leaderboard" : "Standings"}
      className="space-y-5 rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-xl backdrop-blur-xl sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-3">
        <div>
          <h2 className="text-lg font-black tracking-tight text-white sm:text-xl">
            {isGameOver ? "Game Over — Final Standings" : "Current Standings"}
          </h2>
          {isGameOver ? (
            <p className="mt-0.5 text-xs text-slate-300">
              The AI bot fooled the room in{" "}
              <span className="font-bold text-amber-300">{botFooledCount}</span> of {totalRounds}{" "}
              rounds.
            </p>
          ) : null}
        </div>
        {isGameOver ? (
          <span className="rounded-full border border-teal-500/30 bg-teal-500/20 px-3 py-1 font-mono text-xs font-bold text-teal-300 uppercase tracking-wider">
            Final
          </span>
        ) : null}
      </div>

      <ul className="space-y-2.5">
        {entries.map((entry, index) => {
          const rank = entry.rank ?? index + 1;
          const isMe = entry.player_id === myPlayerId;
          const isTopOne = rank === 1 && isGameOver;
          const isTopTwo = rank === 2 && isGameOver;
          const isTopThree = rank === 3 && isGameOver;

          let rankBadge = "border-white/10 bg-black/40 text-slate-400";
          if (isTopOne)
            rankBadge =
              "border-amber-400/50 bg-amber-400/20 text-amber-300 ring-1 ring-amber-400/30";
          else if (isTopTwo) rankBadge = "border-slate-300/40 bg-slate-300/20 text-slate-200";
          else if (isTopThree) rankBadge = "border-amber-700/40 bg-amber-700/20 text-amber-400";

          return (
            <li
              key={entry.player_id}
              className={`flex items-center justify-between rounded-xl border px-4 py-3 transition-all ${
                isTopOne
                  ? "border-amber-400/50 bg-gradient-to-r from-amber-500/15 via-amber-500/5 to-transparent shadow-lg shadow-amber-500/10"
                  : "border-white/10 bg-black/40 hover:border-white/20"
              }`}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-lg border font-mono text-xs font-bold ${rankBadge}`}
                >
                  #{rank}
                </span>
                <span className="text-sm font-bold text-white">{entry.nickname}</span>
                {isMe ? (
                  <span className="rounded-md border border-teal-500/30 bg-teal-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-teal-300">
                    You
                  </span>
                ) : null}
                {entry.is_host ? (
                  <span className="rounded-md border border-amber-500/30 bg-amber-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-300">
                    Host
                  </span>
                ) : null}
              </div>
              <div className="flex items-center gap-2.5">
                {typeof entry.round_points === "number" && entry.round_points > 0 ? (
                  <span className="rounded-full border border-emerald-500/30 bg-emerald-500/20 px-2 py-0.5 font-mono text-xs font-bold text-emerald-300">
                    +{entry.round_points}
                  </span>
                ) : null}
                <span className="font-mono text-sm font-black text-white">{entry.score} pts</span>
              </div>
            </li>
          );
        })}
      </ul>

      {isGameOver && roundsSummary && roundsSummary.length > 0 ? (
        <div className="space-y-2.5 border-t border-white/5 pt-4">
          <h3 className="text-xs font-bold tracking-widest text-teal-400 uppercase">
            Round Breakdown
          </h3>
          <ul className="space-y-2">
            {roundsSummary.map((r) => (
              <li
                key={r.round_number}
                className="rounded-xl border border-white/5 bg-black/40 px-3.5 py-2.5 text-xs shadow-inner"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-bold text-slate-200">
                    Round {r.round_number} — Bot was{" "}
                    <span className="text-rose-300 font-extrabold">{r.bot_alias}</span>
                  </span>
                  <span
                    className={`rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-bold ${
                      r.bot_fooled
                        ? "border-rose-500/30 bg-rose-500/15 text-rose-300"
                        : "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
                    }`}
                  >
                    {r.bot_fooled ? "Bot Fooled Room" : "Bot Spotted"} ({r.votes_for_bot}/
                    {r.human_voters})
                  </span>
                </div>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{r.topic_text}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {isGameOver && roomCode ? <ShareCard roomCode={roomCode} /> : null}

      {isGameOver ? (
        isHost ? (
          <button
            type="button"
            disabled={disabled}
            onClick={onPlayAgain}
            className="min-h-12 w-full rounded-xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 px-5 text-sm font-bold text-slate-950 shadow-lg shadow-teal-500/25 transition-all hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Play Again
          </button>
        ) : (
          <p className="text-center font-mono text-xs text-slate-400">
            Waiting for the host to start another game...
          </p>
        )
      ) : null}
    </section>
  );
}
