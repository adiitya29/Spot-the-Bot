import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "../lib/api";
import { useRoomStore } from "../features/room/roomStore";
import { useRoomSocket } from "../features/room/useRoomSocket";

export function Landing() {
  const [message, setMessage] = useState("");
  const status = useRoomStore((s) => s.status);
  const lastEcho = useRoomStore((s) => s.lastEcho);
  const { sendEcho } = useRoomSocket();

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    sendEcho(trimmed);
    setMessage("");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-8">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
        <span className="inline-block rounded-full bg-teal-500/15 px-3 py-1 text-xs font-medium text-teal-300">
          Phase 0 Scaffold
        </span>
        <h1 className="mt-3 text-3xl font-bold tracking-tight text-white">Spot the Bot</h1>
        <p className="mt-2 text-sm text-slate-400">
          One chat participant is an AI pretending to be human.
        </p>

        <div className="mt-6 space-y-2 rounded-xl border border-slate-800 bg-slate-950/70 p-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-slate-400">API Health</span>
            <span className="font-mono text-xs text-slate-200">
              {healthQuery.isLoading
                ? "checking..."
                : healthQuery.isError
                  ? "offline"
                  : healthQuery.data?.status}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Echo WebSocket</span>
            <span className="font-mono text-xs text-slate-200">{status}</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ping echo socket..."
            aria-label="Ping echo socket"
            className="min-h-11 flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 text-sm text-white placeholder:text-slate-500 focus:border-teal-400 focus:outline-none"
          />
          <button
            type="submit"
            disabled={status !== "connected"}
            className="min-h-11 rounded-xl bg-teal-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Send
          </button>
        </form>

        {lastEcho ? (
          <p className="mt-3 rounded-lg bg-slate-950 p-3 font-mono text-xs text-teal-300">
            Echo: {lastEcho}
          </p>
        ) : null}
      </div>
    </main>
  );
}
