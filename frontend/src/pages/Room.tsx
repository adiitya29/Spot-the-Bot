import { useEffect } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { AnswerBox } from "../features/room/components/AnswerBox";
import { ChatPanel } from "../features/room/components/ChatPanel";
import { Leaderboard } from "../features/room/components/Leaderboard";
import { Lobby } from "../features/room/components/Lobby";
import { PhaseHeader } from "../features/room/components/PhaseHeader";
import { RevealStage } from "../features/room/components/RevealStage";
import { TopicCard } from "../features/room/components/TopicCard";
import { VotePanel } from "../features/room/components/VotePanel";
import { useRoomStore } from "../features/room/roomStore";
import { useRoomSocket } from "../features/room/useRoomSocket";
import { loadRoomSession } from "../lib/api";
import { normalizeRoomCode } from "../lib/constants";

function makeClientMsgId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "00000000-0000-4000-8000-000000000000";
}

export function Room() {
  const { code: rawCode = "" } = useParams();
  const code = normalizeRoomCode(rawCode);
  const session = loadRoomSession(code);

  const roomState = useRoomStore();
  const { dispatch } = roomState;
  const { sendCommand } = useRoomSocket(code, session?.token ?? null);

  useEffect(() => {
    const timer = window.setInterval(() => {
      dispatch({ type: "prune_typing" });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [dispatch]);

  if (!session) {
    return <Navigate to={`/join/${code}`} replace />;
  }

  if (roomState.phase === "lobby") {
    return (
      <Lobby
        room={roomState}
        code={code}
        onStartGame={() => {
          sendCommand("start_game", {});
        }}
        onDismissError={() => {
          roomState.dispatch({ type: "clear_error" });
        }}
      />
    );
  }

  const isOnline = roomState.socketStatus === "connected";
  const mySeat = roomState.seats.find((s) => s.seat_id === roomState.mySeatId) ?? null;
  const me = roomState.players.find((p) => p.id === roomState.myPlayerId) ?? null;
  const isHost = Boolean(me?.is_host);

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col gap-3 px-4 py-5">
      {roomState.socketStatus === "reconnecting" ? (
        <div
          role="status"
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-xs text-amber-200"
        >
          Connection lost. Reconnecting to room...
        </div>
      ) : null}

      {roomState.socketStatus === "evicted" ? (
        <div
          role="alert"
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-xs text-amber-200"
        >
          You opened this room in another tab. This tab is now paused.
        </div>
      ) : null}

      {roomState.socketStatus === "auth_error" ? (
        <div
          role="alert"
          className="flex items-center justify-between rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-200"
        >
          <span>Your guest session expired or is invalid.</span>
          <Link to={`/join/${code}`} className="font-semibold text-white underline">
            Rejoin
          </Link>
        </div>
      ) : null}

      {roomState.lastError ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-200"
        >
          <span>{roomState.lastError.message}</span>
          <button
            type="button"
            onClick={() => roomState.dispatch({ type: "clear_error" })}
            className="font-semibold text-rose-100 underline"
          >
            Dismiss
          </button>
        </div>
      ) : null}

      <PhaseHeader
        code={code}
        phase={roomState.phase}
        roundNumber={roomState.roundNumber}
        totalRounds={roomState.totalRounds}
        phaseEndsAtMs={roomState.phaseEndsAtMs}
        clockOffsetMs={roomState.clockOffsetMs}
        mySeat={mySeat}
      />

      {roomState.topic ? <TopicCard topic={roomState.topic} /> : null}

      {roomState.phase === "answer" ? (
        <AnswerBox
          hasAnswered={roomState.hasAnswered}
          submittedAnswer={roomState.myAnswer}
          disabled={!isOnline}
          onSubmitAnswer={(text) => {
            if (sendCommand("submit_answer", { text })) {
              roomState.dispatch({ type: "answer_submitted_local", text });
            }
          }}
        />
      ) : null}

      {roomState.phase === "chat" ? (
        <ChatPanel
          seats={roomState.seats}
          mySeatId={roomState.mySeatId}
          answers={roomState.answers}
          messages={roomState.messages}
          typingSeats={roomState.typingSeats}
          readyToVote={roomState.readyToVote}
          disabled={!isOnline}
          onSendMessage={(text) =>
            sendCommand("send_message", {
              text,
              client_msg_id: makeClientMsgId(),
            })
          }
          onTyping={(isTyping) => {
            sendCommand("typing", { is_typing: isTyping });
          }}
          onReadyToVote={() => {
            if (sendCommand("ready_to_vote", {})) {
              roomState.dispatch({ type: "ready_to_vote_local" });
            }
          }}
        />
      ) : null}

      {roomState.phase === "vote" ? (
        <VotePanel
          seats={roomState.seats}
          mySeatId={roomState.mySeatId}
          answers={roomState.answers}
          votesCast={roomState.votesCast}
          totalHumans={roomState.totalHumans}
          myVoteTargetSeatId={roomState.myVoteTargetSeatId}
          disabled={!isOnline}
          onCastVote={(targetSeatId) => {
            if (sendCommand("cast_vote", { target_seat_id: targetSeatId })) {
              roomState.dispatch({ type: "vote_cast_local", targetSeatId });
            }
          }}
        />
      ) : null}

      {roomState.phase === "reveal" && roomState.reveal ? (
        <RevealStage
          reveal={roomState.reveal}
          mySeatId={roomState.mySeatId}
          myPlayerId={roomState.myPlayerId}
        />
      ) : null}

      {roomState.phase === "done" && roomState.gameOver ? (
        <Leaderboard
          entries={roomState.gameOver.leaderboard}
          myPlayerId={roomState.myPlayerId}
          roundsSummary={roomState.gameOver.rounds_summary}
          botFooledCount={roomState.gameOver.bot_fooled_count}
          totalRounds={roomState.gameOver.total_rounds}
          isGameOver
          isHost={isHost}
          disabled={!isOnline}
          onPlayAgain={() => {
            sendCommand("play_again", {});
          }}
        />
      ) : null}
    </main>
  );
}
