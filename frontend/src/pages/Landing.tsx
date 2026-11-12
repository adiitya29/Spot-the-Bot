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
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-8">
      <div className="space-y-6">
        <header className="text-center">
          <span className="inline-block rounded-full border border-teal-500/30 bg-teal-500/10 px-3 py-1 text-xs font-semibold tracking-wide text-teal-300 uppercase">
            Social Deduction Party Game
          </span>
          <h1 className="mt-3 text-4xl font-extrabold tracking-tight text-white">Spot the Bot</h1>
          <p className="mt-2 text-sm text-slate-400">
            Chat under random aliases with 4–7 friends. One player in the room is an AI blending in.
          </p>
        </header>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-xl">
          <h2 className="text-lg font-bold text-white">Create a Room</h2>
          <form onSubmit={handleCreate} className="mt-4 space-y-4">
            <div>
              <label htmlFor="create-nickname" className="block text-xs font-medium text-slate-300">
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
                className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 text-sm text-white placeholder:text-slate-500 focus:border-teal-400 focus:outline-none"
              />
            </div>

            <button
              type="button"
              onClick={() => setShowSettings((prev) => !prev)}
              className="text-xs font-medium text-teal-300 hover:text-teal-200"
            >
              {showSettings ? "Hide room settings" : "Customize room settings"}
            </button>

            {showSettings ? (
              <div className="space-y-3 rounded-xl border border-slate-800 bg-slate-950/70 p-3.5 text-sm">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="rounds-input" className="block text-xs text-slate-400">
                      Rounds
                    </label>
                    <input
                      id="rounds-input"
                      type="number"
                      min={1}
                      max={10}
                      value={rounds}
                      onChange={(e) => setRounds(Number(e.target.value) || 3)}
                      className="mt-1 min-h-11 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 text-sm text-white"
                    />
                  </div>
                  <div>
                    <label htmlFor="min-humans-input" className="block text-xs text-slate-400">
                      Min Humans
                    </label>
                    <input
                      id="min-humans-input"
                      type="number"
                      min={3}
                      max={7}
                      value={minHumans}
                      onChange={(e) => setMinHumans(Number(e.target.value) || 3)}
                      className="mt-1 min-h-11 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 text-sm text-white"
                    />
                  </div>
                </div>

                <label className="flex items-start gap-2.5 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={allowReplayUse}
                    onChange={(e) => setAllowReplayUse(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-900 text-teal-500"
                  />
                  <span>
                    Allow anonymized transcript to be featured in solo &ldquo;Guess the Bot&rdquo;
                    replays (disclosed to joining players).
                  </span>
                </label>
              </div>
            ) : null}

            {formError ? (
              <p role="alert" className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                {formError}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={createMutation.isPending}
              className="min-h-11 w-full rounded-xl bg-teal-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {createMutation.isPending ? "Creating room..." : "Create Room"}
            </button>
          </form>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-xl">
          <h2 className="text-lg font-bold text-white">Join with Code</h2>
          <form onSubmit={handleJoinNavigate} className="mt-3 flex gap-2">
            <input
              type="text"
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
              maxLength={ROOM_CODE_LENGTH}
              placeholder="ABC234"
              aria-label="Room code"
              className="min-h-11 flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3.5 font-mono text-sm tracking-widest text-white uppercase placeholder:tracking-normal placeholder:text-slate-500 focus:border-teal-400 focus:outline-none"
            />
            <button
              type="submit"
              className="min-h-11 rounded-xl border border-slate-700 bg-slate-800 px-5 text-sm font-semibold text-white transition hover:bg-slate-700"
            >
              Join
            </button>
          </form>
          {joinError ? (
            <p role="alert" className="mt-2 text-xs text-rose-300">
              {joinError}
            </p>
          ) : null}
        </section>
      </div>
    </main>
  );
}
