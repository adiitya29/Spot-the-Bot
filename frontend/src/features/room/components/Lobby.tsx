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
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-6">
      <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/95 p-5 shadow-xl">
        <header className="flex items-center justify-between gap-2">
          <div>
            <span className="inline-block rounded-full bg-teal-500/15 px-3 py-1 font-mono text-xs font-bold tracking-widest text-teal-300">
              ROOM {code}
            </span>
            <h1 className="mt-2 text-2xl font-bold text-white">Game Lobby</h1>
          </div>
          <Link to="/" className="min-h-11 px-2 py-2 text-xs text-slate-400 hover:text-white">
            Leave
          </Link>
        </header>

        <ConnectionBanner
          status={room.socketStatus}
          code={code}
          error={room.lastError}
          onDismissError={onDismissError}
        />

        <div className="flex gap-2">
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
            className="min-h-11 rounded-xl border border-slate-700 bg-slate-800 px-4 text-xs font-semibold text-white transition hover:bg-slate-700"
          >
            {copied ? "Copied!" : "Copy Link"}
          </button>
        </div>

        <section aria-label="Player roster" className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>
              Players ({connectedCount} / {room.capacity} online)
            </span>
            <span>+1 hidden AI bot</span>
          </div>

          <ul className="space-y-2">
            {room.players.map((player) => (
              <li
                key={player.id}
                className="flex min-h-11 items-center justify-between rounded-xl border border-slate-800 bg-slate-950/70 px-3.5 py-2"
              >
                <div className="flex items-center gap-2.5">
                  <span
                    aria-hidden="true"
                    className={`h-2.5 w-2.5 rounded-full ${
                      player.connected ? "bg-emerald-400" : "bg-amber-400"
                    }`}
                  />
                  <span className="text-sm font-medium text-white">{player.nickname}</span>
                  {player.id === room.myPlayerId ? (
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold text-slate-300 uppercase">
                      You
                    </span>
                  ) : null}
                  {player.is_host ? (
                    <span className="rounded bg-teal-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-teal-300 uppercase">
                      Host
                    </span>
                  ) : null}
                </div>
                <span className="text-xs text-slate-400">
                  {player.connected ? "Online" : "Away"}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <p className="rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs text-slate-400">
          {room.allowReplayUse
            ? "Anonymized public replays are enabled for this room."
            : "Public replays are disabled for this room."}
        </p>

        {me?.is_host ? (
          <div className="space-y-2 pt-1">
            <button
              type="button"
              disabled={!room.canStart || !isOnline}
              onClick={onStartGame}
              className="min-h-11 w-full rounded-xl bg-teal-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Start Game
            </button>
            <p className="text-center text-xs text-slate-400">
              {remainingNeeded > 0
                ? `Need ${remainingNeeded} more connected ${remainingNeeded === 1 ? "player" : "players"} to start (min ${room.minHumans}).`
                : "Ready to start!"}
            </p>
          </div>
        ) : (
          <p className="rounded-xl bg-slate-950/70 py-3 text-center text-xs text-slate-400">
            {!room.canStart && remainingNeeded > 0
              ? `Waiting for ${remainingNeeded} more ${remainingNeeded === 1 ? "player" : "players"} to join...`
              : "Waiting for host to start the game..."}
          </p>
        )}
      </div>
    </main>
  );
}
