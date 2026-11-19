import { useEffect } from "react";
import { getSeatColorTheme } from "../../../lib/constants";
import { playCorrect, playRevealBot, playWrong } from "../../../lib/sound";
import type { RevealPayload } from "../types";
import { Leaderboard } from "./Leaderboard";

interface RevealStageProps {
  reveal: RevealPayload;
  mySeatId: string | null;
  myPlayerId: string | null;
}

export function RevealStage({ reveal, mySeatId, myPlayerId }: RevealStageProps) {
  const isFinalRound = reveal.round_number >= reveal.total_rounds;

  useEffect(() => {
    // Trigger sound effects on reveal
    playRevealBot();

    const myEntry = reveal.tally.find((t) => t.seat_id === mySeatId);
    if (myEntry) {
      if (myEntry.round_points > 0) {
        setTimeout(() => playCorrect(), 600);
      } else {
        setTimeout(() => playWrong(), 600);
      }
    }
  }, [reveal.round_id, reveal.tally, mySeatId]);

  return (
    <div className="space-y-4">
      <section
        aria-label="Bot reveal"
        className={`relative space-y-4 overflow-hidden rounded-2xl border p-5 shadow-2xl backdrop-blur-xl transition-all duration-500 sm:p-6 ${
          reveal.bot_fooled
            ? "border-rose-500/40 bg-gradient-to-b from-rose-950/40 to-slate-900/60 shadow-rose-950/30"
            : "border-emerald-500/40 bg-gradient-to-b from-emerald-950/40 to-slate-900/60 shadow-emerald-950/30"
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-3">
          <span
            className={`inline-flex items-center gap-2 rounded-full px-4 py-1 text-xs font-black tracking-wide uppercase transition-transform animate-pulse shadow-sm ${
              reveal.bot_fooled
                ? "bg-rose-500/25 text-rose-200 border border-rose-500/30"
                : "bg-emerald-500/25 text-emerald-200 border border-emerald-500/30"
            }`}
          >
            <span aria-hidden="true">{reveal.bot_fooled ? "🎭" : "🎯"}</span>
            {reveal.bot_fooled ? "The Bot Fooled You!" : "Bot Spotted!"}
          </span>
          <span className="font-mono text-xs font-semibold text-slate-300">
            {reveal.votes_for_bot}/{reveal.human_voters} caught the bot
          </span>
        </div>

        <div>
          <h2 className="text-xl font-black tracking-tight text-white sm:text-2xl">
            {reveal.bot_alias} was the AI Bot!
          </h2>
          <p className="mt-1 text-xs text-slate-300">
            Everyone who voted for {reveal.bot_alias} earned +100 points.
          </p>
        </div>

        <ul className="space-y-2.5">
          {reveal.tally.map((entry) => {
            const theme = getSeatColorTheme(entry.color_index);
            const isMe = entry.seat_id === mySeatId;
            return (
              <li
                key={entry.seat_id}
                className={`flex items-center justify-between gap-2 rounded-xl border px-4 py-3 transition-all ${
                  entry.is_bot
                    ? "border-rose-500/50 bg-rose-950/30 shadow-lg shadow-rose-950/20"
                    : "border-white/10 bg-black/40"
                }`}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-bold">
                    <span
                      aria-hidden="true"
                      className={`h-2.5 w-2.5 rounded-full ring-2 ring-white/10 ${theme.dot}`}
                    />
                    <span className={theme.text}>{entry.alias}</span>
                    {entry.is_bot ? (
                      <span className="rounded-md border border-rose-500/40 bg-rose-500/20 px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-rose-200">
                        AI Bot
                      </span>
                    ) : (
                      <span className="text-slate-300 font-medium">
                        ({entry.nickname}
                        {isMe ? " — You" : ""})
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2.5">
                  {entry.round_points > 0 ? (
                    <span className="rounded-full border border-emerald-500/30 bg-emerald-500/20 px-2.5 py-0.5 font-mono text-xs font-bold text-emerald-300">
                      +{entry.round_points}
                    </span>
                  ) : null}
                  <span className="font-mono text-xs font-semibold text-slate-400">
                    {entry.votes_received} {entry.votes_received === 1 ? "vote" : "votes"}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>

        <p className="text-center font-mono text-xs text-slate-400 pt-1">
          {isFinalRound ? "Final leaderboard coming up..." : "Next round starting soon..."}
        </p>
      </section>

      <Leaderboard entries={reveal.leaderboard} myPlayerId={myPlayerId} />
    </div>
  );
}
