import { useState } from "react";
import { Link } from "react-router-dom";
import type { RoomState } from "../types";
import { ConnectionBanner } from "./ConnectionBanner";

interface LobbyProps {
  room: RoomState;
  code: string;
  onStartGame: () => void;
  onDismissError: () => void;
}

export function Lobby({ room, code, onStartGame, onDismissError }: LobbyProps) {
  const [copied, setCopied] = useState(false);

  const me = room.players.find((p) => p.id === room.myPlayerId);
  const connectedCount = room.players.filter((p) => p.connected).length;
  const remainingNeeded = Math.max(0, room.minHumans - connectedCount);
  const shareUrl = `${window.location.origin}/join/${code}`;
  const isOnline = room.socketStatus === "connected";

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
    <main className="mx-auto flex min-h-[100dvh] w-full max-w-2xl lg:max-w-3xl flex-col justify-center px-4 py-8 sm:px-6">
      <div className="space-y-6 rounded-3xl border border-white/10 bg-slate-900/60 backdrop-blur-xl p-6 sm:p-8 shadow-2xl shadow-indigo-950/30">
        <header className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-white/5">
          <div>
            <span className="inline-flex items-center gap-2 rounded-xl bg-teal-500/15 border border-teal-500/30 px-3.5 py-1 font-mono text-xs font-bold tracking-widest text-teal-300 shadow-inner">
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse"
              />
              ROOM {code}
            </span>
            <h1 className="mt-2 text-2xl sm:text-3xl font-black tracking-tight text-white">
              Game Lobby
            </h1>
          </div>
          <Link
            to="/"
            className="inline-flex items-center rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-all active:scale-[0.98]"
          >
            &larr; Leave
          </Link>
        </header>

        <ConnectionBanner
          status={room.socketStatus}
          code={code}
          error={room.lastError}
          onDismissError={onDismissError}
        />

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            readOnly
            value={shareUrl}
            aria-label="Invite link"
            className="min-h-12 flex-1 rounded-xl border border-slate-700 bg-slate-950/80 px-4 font-mono text-xs sm:text-sm text-slate-300 select-all focus:outline-none"
          />
          <button
            type="button"
            onClick={() => void handleCopy()}
            className="min-h-12 rounded-xl border border-teal-500/30 bg-teal-500/10 hover:bg-teal-500/20 px-5 text-xs sm:text-sm font-bold text-teal-300 transition-all active:scale-[0.98]"
          >
            {copied ? "Copied!" : "Copy Link"}
          </button>
        </div>

        <section aria-label="Player roster" className="space-y-3">
          <div className="flex items-center justify-between text-xs font-medium text-slate-400">
            <span>
              Players ({connectedCount} / {room.capacity} online)
            </span>
            <span className="text-teal-400/90 font-semibold">+1 hidden AI bot</span>
          </div>

          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {room.players.map((player) => (
              <li
                key={player.id}
                className="flex min-h-12 items-center justify-between rounded-2xl border border-white/5 bg-slate-950/60 px-4 py-2.5 shadow-sm hover:border-white/10 transition-all"
              >
                <div className="flex items-center gap-3">
                  <span
                    aria-hidden="true"
                    className={`h-2.5 w-2.5 rounded-full ${
                      player.connected
                        ? "bg-emerald-400 shadow-sm shadow-emerald-400/50"
                        : "bg-amber-400"
                    }`}
                  />
                  <span className="text-sm font-bold text-white">{player.nickname}</span>
                  {player.id === room.myPlayerId ? (
                    <span className="rounded-md bg-white/10 px-1.5 py-0.5 text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                      You
                    </span>
                  ) : null}
                  {player.is_host ? (
                    <span className="rounded-md bg-teal-500/20 border border-teal-500/30 px-1.5 py-0.5 text-[10px] font-bold text-teal-300 uppercase tracking-wider">
                      Host
                    </span>
                  ) : null}
                </div>
                <span
                  className={`text-xs font-medium ${player.connected ? "text-emerald-400" : "text-amber-400"}`}
                >
                  {player.connected ? "Online" : "Away"}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <p className="rounded-xl border border-white/5 bg-slate-950/40 px-3.5 py-2.5 text-xs text-slate-400 leading-relaxed">
          {room.allowReplayUse
            ? "Anonymized public replays are enabled for this room."
            : "Public replays are disabled for this room."}
        </p>

        {me?.is_host ? (
          <div className="space-y-2 pt-2">
            <button
              type="button"
              disabled={!room.canStart || !isOnline}
              onClick={onStartGame}
              className="min-h-13 w-full rounded-2xl bg-gradient-to-r from-teal-400 via-emerald-400 to-teal-500 px-6 py-3.5 text-base font-black text-slate-950 shadow-xl shadow-teal-500/25 transition-all hover:shadow-teal-400/40 hover:brightness-105 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
            >
              Start Game
            </button>
            <p className="text-center text-xs font-medium text-slate-400">
              {remainingNeeded > 0
                ? `Need ${remainingNeeded} more connected ${remainingNeeded === 1 ? "player" : "players"} to start (min ${room.minHumans}).`
                : "Ready to start!"}
            </p>
          </div>
        ) : (
          <p className="rounded-2xl border border-white/5 bg-slate-950/60 py-4 text-center text-xs font-medium text-slate-400">
            {!room.canStart && remainingNeeded > 0
              ? `Waiting for ${remainingNeeded} more ${remainingNeeded === 1 ? "player" : "players"} to join...`
              : "Waiting for host to start the game..."}
          </p>
        )}
      </div>
    </main>
  );
}
