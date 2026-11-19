import { Link, useParams } from "react-router-dom";
import { ShareCard } from "../features/room/components/ShareCard";
import { normalizeRoomCode } from "../lib/constants";

export function Share() {
  const { code } = useParams<{ code: string }>();
  const cleanCode = normalizeRoomCode(code || "");

  if (!cleanCode) {
    return (
      <main className="mx-auto flex min-h-[100dvh] max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-sm font-bold text-rose-400">Invalid share code</p>
        <Link
          to="/"
          className="rounded-xl border border-white/10 bg-white/5 px-5 py-2.5 text-xs font-bold text-white transition hover:bg-white/10"
        >
          &larr; Back to Home
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-[100dvh] w-full max-w-2xl flex-col justify-center gap-6 px-4 py-10 sm:px-6">
      <header className="text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3.5 py-1 text-xs font-black tracking-widest text-cyan-300 uppercase">
          Match Outcome
        </span>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl">
          Spot the Bot
        </h1>
        <p className="mt-1.5 text-sm text-slate-300">
          One anonymous player was an AI pretending to be human.
        </p>
      </header>

      <ShareCard roomCode={cleanCode} />

      <div className="flex flex-col gap-3">
        <Link
          to="/"
          className="flex min-h-12 w-full items-center justify-center rounded-xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 px-5 text-sm font-black text-slate-950 shadow-xl shadow-teal-500/25 transition-all hover:brightness-110 active:scale-[0.99]"
        >
          Play with Friends (Free)
        </Link>
      </div>
    </main>
  );
}

export default Share;
