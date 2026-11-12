import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { loadRoomSession } from "../lib/api";
import { normalizeRoomCode } from "../lib/constants";

export function Room() {
  const { code: rawCode = "" } = useParams();
  const code = normalizeRoomCode(rawCode);
  const session = loadRoomSession(code);
  const [copied, setCopied] = useState(false);

  if (!session) {
    return <Navigate to={`/join/${code}`} replace />;
  }

  const shareUrl = `${window.location.origin}/join/${code}`;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-8">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <span className="rounded-full bg-teal-500/15 px-3 py-1 font-mono text-xs font-bold tracking-widest text-teal-300">
            ROOM {code}
          </span>
          <Link to="/" className="text-xs text-slate-400 hover:text-slate-200">
            Leave
          </Link>
        </div>

        <h1 className="mt-4 text-2xl font-bold text-white">Lobby Ready for Phase 2</h1>
        <p className="mt-2 text-sm text-slate-400">
          Signed in as <strong className="text-white">{session.nickname}</strong>
          {session.isHost ? " (Host)" : ""}. Your 24h guest token is stored in localStorage.
        </p>

        <div className="mt-5 flex gap-2">
          <input
            type="text"
            readOnly
            value={shareUrl}
            aria-label="Invite link"
            className="min-h-11 flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 font-mono text-xs text-slate-300"
          />
          <button
            type="button"
            onClick={() => void handleCopy()}
            className="min-h-11 rounded-xl bg-slate-800 px-4 text-xs font-semibold text-white hover:bg-slate-700"
          >
            {copied ? "Copied" : "Copy Link"}
          </button>
        </div>
      </div>
    </main>
  );
}
