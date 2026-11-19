import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type BotGlobalStats, type ReplayListItem, getBotStats, getReplays } from "../lib/api";
import { getSoundEnabled, toggleSound } from "../lib/sound";

export function Replays() {
  const [replays, setReplays] = useState<ReplayListItem[]>([]);
  const [stats, setStats] = useState<BotGlobalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [soundOn, setSoundOn] = useState(getSoundEnabled());

  useEffect(() => {
    let mounted = true;
    Promise.all([getReplays(), getBotStats()])
      .then(([replaysData, statsData]) => {
        if (!mounted) return;
        setReplays(replaysData);
        setStats(statsData);
        setLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to load replays");
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const handleToggleSound = () => {
    const next = toggleSound();
    setSoundOn(next);
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 px-4 py-8">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-purple-500/15 px-2.5 py-0.5 text-xs font-bold text-purple-300">
              REPLAYS
            </span>
            <span className="text-xs font-semibold text-slate-400">Match Archive</span>
          </div>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-white sm:text-3xl">
            Guess The Bot
          </h1>
          <p className="text-sm text-slate-400">
            Read real past game chats and guess which anonymous player was secretly an AI.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={handleToggleSound}
            aria-label={soundOn ? "Mute sounds" : "Enable sounds"}
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-800/80 text-sm text-slate-300 transition hover:bg-slate-700"
          >
            {soundOn ? "🔊" : "🔇"}
          </button>
          <Link
            to="/"
            className="flex min-h-10 items-center rounded-xl bg-teal-500 px-4 text-xs font-bold text-slate-950 transition hover:bg-teal-400"
          >
            Back to Home
          </Link>
        </div>
      </header>

      {/* Global Bot Deception Stats Banner */}
      {stats ? (
        <section
          aria-label="Bot statistics"
          className="grid grid-cols-2 gap-3 rounded-2xl border border-purple-500/20 bg-gradient-to-br from-purple-950/30 to-slate-900/60 p-4 sm:grid-cols-4"
        >
          <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3">
            <span className="text-[11px] font-semibold text-slate-400">AI Deception Rate</span>
            <div className="mt-1 text-2xl font-black text-purple-300">
              {Math.round(stats.overall.bot_fooled_rate * 100)}%
            </div>
            <span className="text-[10px] text-slate-500">fooled human voters</span>
          </div>

          <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3">
            <span className="text-[11px] font-semibold text-slate-400">Live Games Played</span>
            <div className="mt-1 text-2xl font-black text-cyan-300">
              {stats.live_games.total_rounds}
            </div>
            <span className="text-[10px] text-slate-500">party rounds</span>
          </div>

          <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3">
            <span className="text-[11px] font-semibold text-slate-400">Solo Replay Guesses</span>
            <div className="mt-1 text-2xl font-black text-emerald-300">
              {stats.solo_replays.total_guesses}
            </div>
            <span className="text-[10px] text-slate-500">solo player attempts</span>
          </div>

          <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3">
            <span className="text-[11px] font-semibold text-slate-400">Solo Accuracy</span>
            <div className="mt-1 text-2xl font-black text-amber-300">
              {stats.solo_replays.total_guesses > 0
                ? `${Math.round(
                    (stats.solo_replays.correct_guesses / stats.solo_replays.total_guesses) * 100,
                  )}%`
                : "—"}
            </div>
            <span className="text-[10px] text-slate-500">identified the AI</span>
          </div>
        </section>
      ) : null}

      {/* Loading & Error States */}
      {loading ? (
        <div className="flex min-h-48 items-center justify-center text-sm font-semibold text-slate-400">
          Loading replay cases...
        </div>
      ) : null}

      {error ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-950/30 p-4 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      {/* Replay Cards Gallery */}
      {!loading && !error && replays.length === 0 ? (
        <div className="flex min-h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 p-8 text-center">
          <span className="text-3xl" aria-hidden="true">
            🤖
          </span>
          <h3 className="mt-2 text-base font-bold text-white">No replays available yet</h3>
          <p className="mt-1 max-w-sm text-xs text-slate-400">
            Play a game in a multiplayer room with friends to generate and publish public replay
            cases!
          </p>
          <Link
            to="/"
            className="mt-4 rounded-xl bg-teal-500 px-4 py-2 text-xs font-bold text-slate-950 transition hover:bg-teal-400"
          >
            Create A Room
          </Link>
        </div>
      ) : null}

      {!loading && !error && replays.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {replays.map((rep) => {
            const fooledPct = Math.round(rep.solo_bot_fooled_rate * 100);
            return (
              <article
                key={rep.id}
                className="flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-md transition hover:border-slate-700 hover:bg-slate-900"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-[10px] font-bold text-cyan-300 uppercase">
                      {rep.topic_category}
                    </span>
                    <span className="font-mono text-[11px] text-slate-400">
                      {rep.human_guesses_count}{" "}
                      {rep.human_guesses_count === 1 ? "guess" : "guesses"}
                    </span>
                  </div>

                  <h2 className="mt-3 text-base font-bold text-white line-clamp-3">
                    &ldquo;{rep.topic_text}&rdquo;
                  </h2>
                </div>

                <div className="mt-5 border-t border-slate-800/80 pt-3">
                  <div className="mb-3 flex items-center justify-between text-xs">
                    <span className="text-slate-400">Deception rate:</span>
                    <span
                      className={`font-mono font-bold ${
                        fooledPct > 50 ? "text-rose-400" : "text-emerald-400"
                      }`}
                    >
                      {rep.human_guesses_count > 0 ? `${fooledPct}% Fooled` : "New Case"}
                    </span>
                  </div>

                  <Link
                    to={`/replays/${rep.id}`}
                    className="flex min-h-10 w-full items-center justify-center rounded-xl bg-purple-600/90 px-4 text-xs font-bold text-white transition hover:bg-purple-500"
                  >
                    Guess The Bot &rarr;
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}
    </main>
  );
}

export default Replays;
