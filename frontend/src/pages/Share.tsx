import { Link, useParams } from "react-router-dom";
import { ShareCard } from "../features/room/components/ShareCard";
import { normalizeRoomCode } from "../lib/constants";

export function Share() {
  const { code } = useParams<{ code: string }>();
  const cleanCode = normalizeRoomCode(code || "");

  if (!cleanCode) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-sm font-semibold text-rose-400">Invalid share code</p>
        <Link
          to="/"
          className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
        >
          &larr; Back to Home
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col gap-6 px-4 py-10">
      <header className="text-center">
        <span className="rounded-full bg-cyan-500/15 px-3 py-1 text-xs font-bold text-cyan-300 uppercase tracking-wider">
          Match Outcome
        </span>
        <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
          Spot the Bot
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          One anonymous player was an AI pretending to be human.
        </p>
      </header>

      <ShareCard roomCode={cleanCode} />

      <div className="flex flex-col gap-3">
        <Link
          to="/"
          className="flex min-h-12 w-full items-center justify-center rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 px-4 text-sm font-bold text-white shadow-lg transition hover:opacity-95"
        >
          Play with Friends (Free)
        </Link>
        <Link
          to="/replays"
          className="flex min-h-11 w-full items-center justify-center rounded-xl border border-slate-700 bg-slate-800/80 px-4 text-xs font-bold text-slate-300 transition hover:bg-slate-700"
        >
          Play Solo &ldquo;Guess the Bot&rdquo; Replays &rarr;
        </Link>
      </div>
    </main>
  );
}

export default Share;

