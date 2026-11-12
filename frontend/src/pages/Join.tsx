import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, getRoom, joinRoom, saveRoomSession } from "../lib/api";
import { NICKNAME_MAX_LENGTH, NICKNAME_MIN_LENGTH, normalizeRoomCode } from "../lib/constants";

export function Join() {
  const { code: rawCode = "" } = useParams();
  const code = normalizeRoomCode(rawCode);
  const navigate = useNavigate();

  const [nickname, setNickname] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-8">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <span className="font-mono text-sm font-bold tracking-widest text-teal-300">
            ROOM {code}
          </span>
          <Link to="/" className="text-xs text-slate-400 hover:text-slate-200">
            Back home
          </Link>
        </div>

        <h1 className="mt-3 text-2xl font-bold text-white">Join Game</h1>

        {roomQuery.isLoading ? (
          <p className="mt-4 text-sm text-slate-400">Checking room availability...</p>
        ) : roomQuery.isError ? (
          <div className="mt-4 space-y-4">
            <p role="alert" className="rounded-xl bg-rose-500/10 p-3 text-sm text-rose-300">
              Room {code} was not found. Check the code and try again.
            </p>
            <Link
              to="/"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-slate-800 text-sm font-semibold text-white hover:bg-slate-700"
            >
              Return Home
            </Link>
          </div>
        ) : room ? (
          <>
            <div className="mt-4 space-y-2 rounded-xl border border-slate-800 bg-slate-950/70 p-4 text-xs text-slate-300">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Seats Filled</span>
                <span className="font-semibold text-white">
                  {room.human_count} / {room.capacity} humans (+1 hidden bot)
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Status</span>
                <span className="font-mono text-teal-300 uppercase">{room.status}</span>
              </div>
              <p className="border-t border-slate-800 pt-2 text-slate-400">
                {room.allow_replay_use
                  ? "Privacy notice: Host enabled anonymized public replays for this room."
                  : "Privacy notice: Public replays are disabled for this room."}
              </p>
            </div>

            {blockedReason ? (
              <p
                role="alert"
                className="mt-4 rounded-xl bg-amber-500/10 p-3 text-sm text-amber-300"
              >
                {blockedReason}
              </p>
            ) : (
              <form onSubmit={handleJoin} className="mt-5 space-y-4">
                <div>
                  <label
                    htmlFor="join-nickname"
                    className="block text-xs font-medium text-slate-300"
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
                    className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 text-sm text-white placeholder:text-slate-500 focus:border-teal-400 focus:outline-none"
                  />
                </div>

                {errorMsg ? (
                  <p
                    role="alert"
                    className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300"
                  >
                    {errorMsg}
                  </p>
                ) : null}

                <button
                  type="submit"
                  disabled={joinMutation.isPending}
                  className="min-h-11 w-full rounded-xl bg-teal-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-60"
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
