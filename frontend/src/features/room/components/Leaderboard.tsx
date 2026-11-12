import type { LeaderboardEntry, RoundSummaryEntry } from "../types";

interface LeaderboardProps {
  entries: LeaderboardEntry[];
  myPlayerId: string | null;
  roundsSummary?: RoundSummaryEntry[];
  botFooledCount?: number;
  totalRounds?: number;
  isGameOver?: boolean;
  isHost?: boolean;
  disabled?: boolean;
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
  onPlayAgain,
}: LeaderboardProps) {
  return (
    <section
      aria-label={isGameOver ? "Final leaderboard" : "Standings"}
      className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/95 p-5 shadow-lg"
    >
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-bold text-white">
            {isGameOver ? "Game Over — Final Standings" : "Current Standings"}
          </h2>
          {isGameOver ? (
            <p className="text-xs text-slate-400">
              The AI bot fooled the room in {botFooledCount} of {totalRounds} rounds.
            </p>
          ) : null}
        </div>
        {isGameOver ? (
          <span className="rounded-full bg-teal-500/15 px-3 py-1 text-xs font-semibold text-teal-300">
            Final
          </span>
        ) : null}
      </div>

      <ul className="space-y-2">
        {entries.map((entry, index) => {
          const rank = entry.rank ?? index + 1;
          const isMe = entry.player_id === myPlayerId;
          return (
            <li
              key={entry.player_id}
              className={`flex items-center justify-between rounded-xl border px-3.5 py-2.5 ${
                rank === 1 && isGameOver
                  ? "border-amber-400/40 bg-amber-500/10"
                  : "border-slate-800 bg-slate-950/70"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <span className="w-6 font-mono text-xs font-bold text-slate-400">#{rank}</span>
                <span className="text-sm font-semibold text-white">{entry.nickname}</span>
                {isMe ? (
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-teal-300">
                    You
                  </span>
                ) : null}
                {entry.is_host ? (
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-amber-300">
                    Host
                  </span>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                {typeof entry.round_points === "number" && entry.round_points > 0 ? (
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-emerald-300">
                    +{entry.round_points}
                  </span>
                ) : null}
                <span className="font-mono text-sm font-bold text-white">{entry.score} pts</span>
              </div>
            </li>
          );
        })}
      </ul>

      {isGameOver && roundsSummary && roundsSummary.length > 0 ? (
        <div className="space-y-2 border-t border-slate-800 pt-3">
          <h3 className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
            Round Breakdown
          </h3>
          <ul className="space-y-2">
            {roundsSummary.map((r) => (
              <li
                key={r.round_number}
                className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-200">
                    Round {r.round_number} — Bot was {r.bot_alias}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      r.bot_fooled
                        ? "bg-rose-500/15 text-rose-300"
                        : "bg-emerald-500/15 text-emerald-300"
                    }`}
                  >
                    {r.bot_fooled ? "Bot Fooled Room" : "Bot Spotted"} ({r.votes_for_bot}/
                    {r.human_voters})
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-slate-400">{r.topic_text}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {isGameOver ? (
        isHost ? (
          <button
            type="button"
            disabled={disabled}
            onClick={onPlayAgain}
            className="min-h-11 w-full rounded-xl bg-teal-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Play Again
          </button>
        ) : (
          <p className="text-center text-xs text-slate-400">
            Waiting for the host to start another game...
          </p>
        )
      ) : null}
    </section>
  );
}
