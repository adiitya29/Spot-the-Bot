import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { type ReplayDetail, type SoloGuessResponse, getReplay, submitSoloGuess } from "../lib/api";
import { getSeatColorTheme } from "../lib/constants";
import { getSoundEnabled, playCorrect, playTick, playWrong, toggleSound } from "../lib/sound";

export function ReplayPlay() {
  const { id } = useParams<{ id: string }>();

  const [replay, setReplay] = useState<ReplayDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedAlias, setSelectedAlias] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState<SoloGuessResponse | null>(null);
  const [soundOn, setSoundOn] = useState(getSoundEnabled());

  useEffect(() => {
    if (!id) return;
    let mounted = true;

    getReplay(id)
      .then((data) => {
        if (!mounted) return;
        setReplay(data);
        setLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to load replay");
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [id]);

  const handleToggleSound = () => {
    const next = toggleSound();
    setSoundOn(next);
  };

  const handleSelectAlias = (alias: string) => {
    if (outcome) return;
    playTick();
    setSelectedAlias(alias);
  };

  const handleSubmitGuess = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !selectedAlias || submitting || outcome) return;

    setSubmitting(true);
    try {
      const res = await submitSoloGuess(id, selectedAlias);
      setOutcome(res);
      if (res.correct) {
        playCorrect();
      } else {
        playWrong();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit guess");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg items-center justify-center px-4">
        <p className="text-sm font-semibold text-slate-400">Loading replay case...</p>
      </main>
    );
  }

  if (error || !replay) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-sm font-semibold text-rose-400">{error || "Replay not found"}</p>
        <Link
          to="/replays"
          className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
        >
          &larr; Back to Replays
        </Link>
      </main>
    );
  }

  const participants = replay.transcript.participants || [];
  const answers = replay.transcript.answers || [];
  const messages = replay.transcript.messages || [];

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 px-4 py-6">
      {/* Navigation header */}
      <nav className="flex items-center justify-between border-b border-slate-800 pb-3">
        <Link
          to="/replays"
          className="text-xs font-semibold text-teal-400 transition hover:text-teal-300"
        >
          &larr; All Replays
        </Link>

        <div className="flex items-center gap-3">
          <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-[11px] font-mono text-slate-300">
            Room #{replay.room_code}
          </span>
          <button
            type="button"
            onClick={handleToggleSound}
            aria-label={soundOn ? "Mute sounds" : "Enable sounds"}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-700 bg-slate-800 text-xs text-slate-300"
          >
            {soundOn ? "🔊" : "🔇"}
          </button>
        </div>
      </nav>

      {/* Topic Card */}
      <section
        aria-label="Round topic"
        className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-lg"
      >
        <span className="rounded-full bg-purple-500/15 px-2.5 py-0.5 text-[10px] font-bold text-purple-300 uppercase">
          {replay.topic_category} Topic
        </span>
        <h1 className="mt-2 text-lg font-bold text-white sm:text-xl">
          &ldquo;{replay.topic_text}&rdquo;
        </h1>
      </section>

      {/* Opening Answers */}
      {answers.length > 0 ? (
        <section
          aria-label="Initial answers"
          className="space-y-2.5 rounded-2xl border border-slate-800 bg-slate-900/60 p-4"
        >
          <h2 className="text-xs font-bold tracking-wider text-slate-400 uppercase">
            Opening Answers
          </h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {answers.map((ans, idx) => {
              const part = participants.find((p) => p.seat_id === ans.seat_id);
              const theme = getSeatColorTheme(part?.color_index ?? idx);
              return (
                <div
                  key={ans.seat_id || idx}
                  className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-3"
                >
                  <div className="flex items-center gap-2">
                    <span aria-hidden="true" className={`h-2 w-2 rounded-full ${theme.dot}`} />
                    <span className={`text-xs font-bold ${theme.text}`}>{ans.alias}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-200">{ans.text}</p>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {/* Chat Transcript Timeline */}
      <section
        aria-label="Chat transcript"
        className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/95 p-4 shadow-md"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold tracking-wider text-slate-400 uppercase">
            Chat Transcript ({messages.length} messages)
          </h2>
          <span className="text-[11px] text-slate-500">Read and spot the AI</span>
        </div>

        <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
          {messages.map((m) => {
            const part = participants.find((p) => p.seat_id === m.seat_id);
            const theme = getSeatColorTheme(part?.color_index ?? 0);
            const latencySec = (m.latency_ms / 1000).toFixed(1);
            return (
              <div
                key={m.id}
                className="flex flex-col gap-0.5 rounded-xl border border-slate-800/60 bg-slate-950/60 p-2.5 text-xs"
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className={`font-bold ${theme.text}`}>{m.alias}</span>
                  <span className="font-mono text-[10px] text-slate-500">{latencySec}s</span>
                </div>
                <p className="text-slate-200">{m.text}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Solo Guess Voting Section (Before submission) */}
      {!outcome ? (
        <form
          onSubmit={handleSubmitGuess}
          aria-label="Guess the bot form"
          className="space-y-4 rounded-2xl border border-purple-500/30 bg-purple-950/20 p-5 shadow-lg"
        >
          <div>
            <h2 className="text-base font-bold text-white">Who is the covert AI Bot?</h2>
            <p className="mt-0.5 text-xs text-slate-300">
              Select the player whose typing style, tone, or timing looks like AI.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {participants.map((p) => {
              const theme = getSeatColorTheme(p.color_index);
              const isSelected = selectedAlias === p.alias;
              return (
                <button
                  key={p.seat_id}
                  type="button"
                  onClick={() => handleSelectAlias(p.alias)}
                  className={`flex items-center gap-2.5 rounded-xl border p-3 text-left transition ${
                    isSelected
                      ? "border-purple-400 bg-purple-600/30 shadow-md shadow-purple-950/40"
                      : "border-slate-800 bg-slate-950/70 hover:border-slate-700"
                  }`}
                >
                  <span aria-hidden="true" className={`h-3 w-3 rounded-full ${theme.dot}`} />
                  <span className={`text-xs font-bold ${theme.text}`}>{p.alias}</span>
                </button>
              );
            })}
          </div>

          <button
            type="submit"
            disabled={!selectedAlias || submitting}
            className="flex min-h-11 w-full items-center justify-center rounded-xl bg-purple-600 px-4 text-sm font-bold text-white transition hover:bg-purple-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Checking Guess..." : "Submit Guess"}
          </button>
        </form>
      ) : null}

      {/* Reveal Outcome Card (After submission) */}
      {outcome ? (
        <section
          aria-label="Solo guess outcome"
          className={`space-y-4 rounded-2xl border p-5 shadow-xl transition-all animate-in fade-in duration-300 ${
            outcome.correct
              ? "border-emerald-500/50 bg-emerald-950/30"
              : "border-rose-500/50 bg-rose-950/30"
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs font-bold tracking-wide uppercase ${
                outcome.correct
                  ? "bg-emerald-500/20 text-emerald-200"
                  : "bg-rose-500/20 text-rose-200"
              }`}
            >
              {outcome.correct ? "🎯 Correct! Bot Spotted" : "🎭 Fooled! Wrong Guess"}
            </span>
            <span className="font-mono text-xs text-slate-300">Bot was {outcome.bot_alias}</span>
          </div>

          <div>
            <h2 className="text-xl font-extrabold text-white">
              {outcome.correct
                ? `You caught the bot! It was ${outcome.bot_alias}.`
                : `Fooled! The AI was actually ${outcome.bot_alias}.`}
            </h2>
            <p className="mt-1 text-xs text-slate-300">{outcome.explanation}</p>
          </div>

          <div className="grid grid-cols-2 gap-3 border-t border-slate-800/60 pt-3">
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              <span className="text-[11px] font-semibold text-slate-400">Solo Accuracy</span>
              <div className="mt-0.5 text-lg font-extrabold text-cyan-300">
                {Math.round(outcome.solo_accuracy_rate * 100)}%
              </div>
              <span className="text-[10px] text-slate-500">spotted the bot</span>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              <span className="text-[11px] font-semibold text-slate-400">Total Attempts</span>
              <div className="mt-0.5 text-lg font-extrabold text-purple-300">
                {outcome.human_guesses_count}
              </div>
              <span className="text-[10px] text-slate-500">solo players</span>
            </div>
          </div>

          <div className="flex flex-col gap-2 pt-2 sm:flex-row">
            <Link
              to="/replays"
              className="flex min-h-10 flex-1 items-center justify-center rounded-xl bg-purple-600 px-4 text-xs font-bold text-white transition hover:bg-purple-500"
            >
              Try Another Replay &rarr;
            </Link>
            <Link
              to="/"
              className="flex min-h-10 flex-1 items-center justify-center rounded-xl border border-slate-700 bg-slate-800 px-4 text-xs font-bold text-slate-200 transition hover:bg-slate-700"
            >
              Play Live with Friends
            </Link>
          </div>
        </section>
      ) : null}
    </main>
  );
}

export default ReplayPlay;
