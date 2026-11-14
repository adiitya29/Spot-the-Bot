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
    <div className="space-y-3">
      <section
        aria-label="Bot reveal"
        className={`relative space-y-3 overflow-hidden rounded-2xl border p-5 shadow-xl transition-all duration-500 ${
          reveal.bot_fooled
            ? "border-rose-500/50 bg-rose-950/30 shadow-rose-950/20"
            : "border-emerald-500/50 bg-emerald-950/30 shadow-emerald-950/20"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1 text-xs font-bold tracking-wide uppercase transition-transform animate-pulse ${
              reveal.bot_fooled
                ? "bg-rose-500/20 text-rose-200"
                : "bg-emerald-500/20 text-emerald-200"
            }`}
          >
            <span aria-hidden="true">{reveal.bot_fooled ? "🎭" : "🎯"}</span>
            {reveal.bot_fooled ? "The Bot Fooled You!" : "Bot Spotted!"}
          </span>
          <span className="font-mono text-xs text-slate-300">
            {reveal.votes_for_bot}/{reveal.human_voters} caught the bot
          </span>
        </div>

        <div>
          <h2 className="text-xl font-extrabold text-white">{reveal.bot_alias} was the AI Bot!</h2>
          <p className="mt-0.5 text-xs text-slate-300">
            Everyone who voted for {reveal.bot_alias} earned +100 points.
          </p>
        </div>

        <ul className="space-y-2">
          {reveal.tally.map((entry) => {
            const theme = getSeatColorTheme(entry.color_index);
            const isMe = entry.seat_id === mySeatId;
            return (
              <li
                key={entry.seat_id}
                className={`flex items-center justify-between gap-2 rounded-xl border px-3.5 py-2.5 transition-all ${
                  entry.is_bot
                    ? "border-rose-500/60 bg-slate-950/90 shadow-md shadow-rose-950/30"
                    : "border-slate-800 bg-slate-950/70"
                }`}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                    <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${theme.dot}`} />
                    <span className={theme.text}>{entry.alias}</span>
                    {entry.is_bot ? (
                      <span className="rounded bg-rose-500/25 px-1.5 py-0.5 text-[10px] font-extrabold text-rose-200 uppercase tracking-wider">
                        AI Bot
                      </span>
                    ) : (
                      <span className="text-slate-300">
                        ({entry.nickname}
                        {isMe ? " — You" : ""})
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {entry.round_points > 0 ? (
                    <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 font-mono text-[11px] font-bold text-emerald-300">
                      +{entry.round_points}
                    </span>
                  ) : null}
                  <span className="font-mono text-xs text-slate-400">
                    {entry.votes_received} {entry.votes_received === 1 ? "vote" : "votes"}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>

        <p className="text-center text-xs text-slate-400">
          {isFinalRound ? "Final leaderboard coming up..." : "Next round starting soon..."}
        </p>
      </section>

      <Leaderboard entries={reveal.leaderboard} myPlayerId={myPlayerId} />
    </div>
  );
}
