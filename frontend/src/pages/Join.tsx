import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, getRoom, joinRoom, saveRoomSession, warmupBackend } from "../lib/api";
import { NICKNAME_MAX_LENGTH, NICKNAME_MIN_LENGTH, normalizeRoomCode } from "../lib/constants";

export function Join() {
  const { code: rawCode = "" } = useParams();
  const code = normalizeRoomCode(rawCode);
  const navigate = useNavigate();

  const [nickname, setNickname] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    void warmupBackend();
  }, []);

  const roomQuery = useQuery({
    queryKey: ["room", code],
    queryFn: () => getRoom(code),
    enabled: code.length > 0,
    retry: false,
  });

  const joinMutation = useMutation({
    mutationFn: () => joinRoom(code, nickname.trim()),
    onSuccess: (data) => {
      saveRoomSession({
        roomCode: data.room.code,
        playerId: data.player.id,
        nickname: data.player.nickname,
        token: data.player_token,
        isHost: data.player.is_host,
      });
      navigate(`/r/${data.room.code}`);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Unable to join this room.");
      }
    },
  });

  function handleJoin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (joinMutation.isPending) {
      return;
    }
    const trimmed = nickname.trim();
    if (trimmed.length < NICKNAME_MIN_LENGTH || trimmed.length > NICKNAME_MAX_LENGTH) {
      setErrorMsg(
        `Nickname must be between ${NICKNAME_MIN_LENGTH} and ${NICKNAME_MAX_LENGTH} characters.`,
      );
      return;
    }
    setErrorMsg(null);
    joinMutation.mutate();
  }

  const room = roomQuery.data;
  const isFull = room ? room.human_count >= room.capacity : false;
  const isClosed = room ? room.status !== "lobby" : false;
  const blockedReason =
    room?.status === "in_progress"
      ? "This game has already started."
      : isClosed
        ? "This room is no longer accepting players."
        : isFull
          ? "This room is full."
          : null;

  return (
    <main className="mx-auto flex min-h-[100dvh] w-full max-w-xl flex-col justify-center px-4 py-8 sm:px-6">
      <div className="rounded-3xl border border-white/10 bg-slate-900/60 backdrop-blur-xl p-6 sm:p-8 shadow-2xl shadow-indigo-950/30">
        <div className="flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-500/15 border border-teal-500/30 px-3.5 py-1 font-mono text-xs font-bold tracking-widest text-teal-300 shadow-inner">
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse"
            />
            ROOM {code}
          </span>
          <Link
            to="/"
            className="text-xs font-medium text-slate-400 hover:text-white transition-colors"
          >
            &larr; Back home
          </Link>
        </div>

        <h1 className="mt-4 text-3xl font-black tracking-tight text-white">Join Game</h1>

        {roomQuery.isLoading ? (
          <p className="mt-4 text-sm text-slate-400 animate-pulse">Checking room availability...</p>
        ) : roomQuery.isError ? (
          <div className="mt-5 space-y-4">
            <p
              role="alert"
              className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm font-medium text-rose-300"
            >
              {roomQuery.error instanceof ApiError && roomQuery.error.status !== 404
                ? roomQuery.error.message
                : `Room ${code} was not found. Check the code and try again.`}
            </p>
            <Link
              to="/"
              className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-slate-800 text-sm font-bold text-white transition hover:bg-slate-700"
            >
              Return Home
            </Link>
          </div>
        ) : room ? (
          <>
            <div className="mt-5 space-y-3 rounded-2xl border border-white/10 bg-black/40 p-4 text-xs text-slate-300 shadow-inner">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Seats Filled</span>
                <span className="font-semibold text-white">
                  {room.human_count} / {room.capacity} humans (+1 hidden bot)
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Status</span>
                <span className="rounded-md border border-teal-500/30 bg-teal-500/15 px-2.5 py-0.5 font-mono text-[11px] font-bold text-teal-300 uppercase">
                  {room.status}
                </span>
              </div>
              <p className="border-t border-white/5 pt-2.5 text-slate-400 leading-relaxed">
                {room.allow_replay_use
                  ? "Privacy notice: Host enabled anonymized public replays for this room."
                  : "Privacy notice: Public replays are disabled for this room."}
              </p>
            </div>

            {blockedReason ? (
              <p
                role="alert"
                className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm font-medium text-amber-300"
              >
                {blockedReason}
              </p>
            ) : (
              <form onSubmit={handleJoin} className="mt-6 space-y-4">
                <div>
                  <label
                    htmlFor="join-nickname"
                    className="block text-xs font-semibold tracking-wide text-slate-300 uppercase"
                  >
                    Choose Nickname
                  </label>
                  <input
                    id="join-nickname"
                    type="text"
                    value={nickname}
                    onChange={(e) => setNickname(e.target.value)}
                    minLength={NICKNAME_MIN_LENGTH}
                    maxLength={NICKNAME_MAX_LENGTH}
                    placeholder="2–20 characters"
                    className="mt-1.5 min-h-12 w-full rounded-xl border border-white/10 bg-black/50 px-4 text-base text-white placeholder:text-slate-500 shadow-inner focus:border-teal-400 focus:bg-slate-950 focus:ring-1 focus:ring-teal-400/40 focus:outline-none transition-all"
                  />
                </div>

                {errorMsg ? (
                  <p
                    role="alert"
                    className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs font-medium text-rose-300"
                  >
                    {errorMsg}
                  </p>
                ) : null}

                <button
                  type="submit"
                  disabled={joinMutation.isPending}
                  className="min-h-12 w-full rounded-xl bg-gradient-to-r from-teal-400 via-emerald-400 to-teal-500 px-6 py-3 text-base font-bold text-slate-950 shadow-lg shadow-teal-500/20 transition-all hover:shadow-teal-400/30 hover:brightness-105 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {joinMutation.isPending ? "Joining..." : "Join Lobby"}
                </button>
              </form>
            )}
          </>
        ) : null}
      </div>
    </main>
  );
}
