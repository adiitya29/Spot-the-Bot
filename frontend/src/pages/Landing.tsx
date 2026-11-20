import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ApiError, createRoom, saveRoomSession } from "../lib/api";
import {
  NICKNAME_MAX_LENGTH,
  NICKNAME_MIN_LENGTH,
  ROOM_CODE_LENGTH,
  normalizeRoomCode,
} from "../lib/constants";

export function Landing() {
  const navigate = useNavigate();
  const [nickname, setNickname] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [rounds, setRounds] = useState(3);
  const [minHumans, setMinHumans] = useState(3);
  const [allowReplayUse, setAllowReplayUse] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [joinError, setJoinError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createRoom(nickname.trim(), {
        rounds,
        min_humans: minHumans,
        allow_replay_use: allowReplayUse,
      }),
    onSuccess: (data) => {
      saveRoomSession({
        roomCode: data.code,
        playerId: data.player.id,
        nickname: data.player.nickname,
        token: data.player_token,
        isHost: data.player.is_host,
      });
      navigate(`/r/${data.code}`);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("Unable to create room right now.");
      }
    },
  });

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = nickname.trim();
    if (trimmed.length < NICKNAME_MIN_LENGTH || trimmed.length > NICKNAME_MAX_LENGTH) {
      setFormError(
        `Nickname must be between ${NICKNAME_MIN_LENGTH} and ${NICKNAME_MAX_LENGTH} characters.`,
      );
      return;
    }
    setFormError(null);
    createMutation.mutate();
  }

  function handleJoinNavigate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = normalizeRoomCode(joinCode);
    if (code.length !== ROOM_CODE_LENGTH) {
      setJoinError(`Enter a ${ROOM_CODE_LENGTH}-character room code.`);
      return;
    }
    setJoinError(null);
    navigate(`/join/${code}`);
  }

  return (
    <main className="mx-auto flex min-h-[100dvh] w-full max-w-5xl flex-col justify-center px-4 py-8 sm:px-6 lg:px-8">
      <div className="space-y-8">
        <header className="text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 px-3.5 py-1 text-xs font-semibold tracking-wider text-teal-300 uppercase shadow-inner">
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse"
            />
            Social Deduction Party Game
          </span>
          <h1 className="mt-3 text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-100 to-slate-400">
            Spot the Bot
          </h1>
          <p className="mt-3 text-sm sm:text-base max-w-xl mx-auto text-slate-300 leading-relaxed">
            Chat under random aliases with 4–7 friends. One player in the room is secretly an AI
            blending in.
          </p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
          <section className="md:col-span-7 rounded-3xl border border-white/10 bg-slate-900/60 backdrop-blur-xl p-6 sm:p-8 shadow-2xl shadow-indigo-950/30 hover:border-white/15 transition-all">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold tracking-tight text-white">Create a Room</h2>
              <span className="text-xs font-medium text-teal-400/80 bg-teal-500/10 px-2.5 py-1 rounded-full border border-teal-500/20">
                Host Game
              </span>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label
                  htmlFor="create-nickname"
                  className="block text-xs font-semibold tracking-wide text-slate-300 uppercase"
                >
                  Your Nickname
                </label>
                <input
                  id="create-nickname"
                  type="text"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  minLength={NICKNAME_MIN_LENGTH}
                  maxLength={NICKNAME_MAX_LENGTH}
                  placeholder="e.g. Alex"
                  className="mt-1.5 min-h-12 w-full rounded-xl border border-slate-700 bg-slate-950/80 px-4 text-base text-white placeholder:text-slate-500 focus:border-teal-400 focus:ring-2 focus:ring-teal-400/20 focus:outline-none transition-all"
                />
              </div>

              <div>
                <button
                  type="button"
                  onClick={() => setShowSettings((prev) => !prev)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-teal-300 hover:text-teal-200 transition-colors"
                >
                  <span aria-hidden="true">{showSettings ? "▾" : "▸"}</span>
                  {showSettings ? "Hide room settings" : "Customize room settings"}
                </button>
              </div>

              {showSettings ? (
                <div className="space-y-3.5 rounded-2xl border border-slate-800 bg-slate-950/60 p-4 text-sm animate-in fade-in duration-200">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label
                        htmlFor="rounds-input"
                        className="block text-xs font-medium text-slate-400"
                      >
                        Rounds
                      </label>
                      <input
                        id="rounds-input"
                        type="number"
                        min={1}
                        max={10}
                        value={rounds}
                        onChange={(e) => setRounds(Number(e.target.value) || 3)}
                        className="mt-1 min-h-11 w-full rounded-xl border border-slate-700 bg-slate-900 px-3 text-sm text-white focus:border-teal-400 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="min-humans-input"
                        className="block text-xs font-medium text-slate-400"
                      >
                        Min Humans
                      </label>
                      <input
                        id="min-humans-input"
                        type="number"
                        min={3}
                        max={7}
                        value={minHumans}
                        onChange={(e) => setMinHumans(Number(e.target.value) || 3)}
                        className="mt-1 min-h-11 w-full rounded-xl border border-slate-700 bg-slate-900 px-3 text-sm text-white focus:border-teal-400 focus:outline-none"
                      />
                    </div>
                  </div>

                  <label className="flex items-start gap-2.5 text-xs text-slate-300 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={allowReplayUse}
                      onChange={(e) => setAllowReplayUse(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-900 text-teal-500 focus:ring-teal-400/20"
                    />
                    <span className="leading-relaxed">
                      Allow anonymized transcript for public match replays and research (disclosed
                      to joining players).
                    </span>
                  </label>
                </div>
              ) : null}

              {formError ? (
                <p
                  role="alert"
                  className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs font-medium text-rose-300"
                >
                  {formError}
                </p>
              ) : null}

              <button
                type="submit"
                disabled={createMutation.isPending}
                className="min-h-12 w-full rounded-xl bg-gradient-to-r from-teal-400 via-emerald-400 to-teal-500 px-6 py-3 text-base font-bold text-slate-950 shadow-lg shadow-teal-500/20 transition-all hover:shadow-teal-400/30 hover:brightness-105 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {createMutation.isPending ? "Creating room..." : "Create Room"}
              </button>
            </form>
          </section>

          {/* Join with Code (5 cols) */}
          <section className="md:col-span-5 flex flex-col justify-between rounded-3xl border border-white/10 bg-slate-900/60 backdrop-blur-xl p-6 sm:p-8 shadow-2xl shadow-indigo-950/30 hover:border-white/15 transition-all">
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold tracking-tight text-white">Join with Code</h2>
                <span className="text-xs font-semibold text-teal-400 bg-teal-500/10 px-3 py-1 rounded-full border border-teal-500/20">
                  Join Match
                </span>
              </div>

              <form onSubmit={handleJoinNavigate} className="space-y-4">
                <div>
                  <label
                    htmlFor="join-room-code"
                    className="block text-xs font-semibold tracking-wide text-slate-300 uppercase"
                  >
                    Room Code
                  </label>
                  <input
                    id="join-room-code"
                    type="text"
                    value={joinCode}
                    onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                    maxLength={ROOM_CODE_LENGTH}
                    placeholder="ABC234"
                    aria-label="Room code"
                    className="mt-1.5 min-h-12 h-12 w-full rounded-xl border border-white/10 bg-black/50 px-4 text-center font-mono text-lg font-bold tracking-[0.25em] text-white uppercase placeholder:tracking-normal placeholder:font-normal placeholder:text-slate-500 shadow-inner focus:border-teal-400 focus:bg-slate-950 focus:ring-1 focus:ring-teal-400/40 focus:outline-none transition-all"
                  />
                  <p className="mt-2 text-center text-xs text-slate-400">
                    Have a 6-character room code from a friend? Enter it above.
                  </p>
                </div>

                {joinError ? (
                  <p
                    role="alert"
                    className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-center text-xs font-medium text-rose-300"
                  >
                    {joinError}
                  </p>
                ) : null}

                <button
                  type="submit"
                  className="min-h-12 w-full rounded-xl bg-gradient-to-r from-teal-400 via-emerald-400 to-teal-500 px-6 py-3 text-base font-bold text-slate-950 shadow-lg shadow-teal-500/20 transition-all hover:shadow-teal-400/30 hover:brightness-105 active:scale-[0.98]"
                >
                  Join Room
                </button>
              </form>
            </div>

            <div className="mt-6 space-y-2.5 rounded-2xl border border-white/5 bg-black/40 p-4 text-xs text-slate-300 shadow-inner">
              <div className="flex items-center gap-2 text-slate-300">
                <span className="text-teal-400 font-bold">✓</span>
                <span>Instant guest play — no signup required</span>
              </div>
              <div className="flex items-center gap-2 text-slate-300">
                <span className="text-teal-400 font-bold">✓</span>
                <span>Works on all phone and desktop browsers</span>
              </div>
              <div className="flex items-center gap-2 text-slate-300">
                <span className="text-teal-400 font-bold">✓</span>
                <span>Synced live countdowns and private voting</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
