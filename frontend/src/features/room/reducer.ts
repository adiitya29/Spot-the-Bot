import { computeClockOffset } from "../../lib/clockSync";
import type { LeaderboardEntry, LobbyPlayer, RoomAction, RoomState } from "./types";

const TYPING_TTL_MS = 4000;

function mergePlayerScores(players: LobbyPlayer[], leaderboard: LeaderboardEntry[]): LobbyPlayer[] {
  const byId = new Map(leaderboard.map((entry) => [entry.player_id, entry]));
  return players.map((player) => {
    const updated = byId.get(player.id);
    return updated ? { ...player, score: updated.score } : player;
  });
}

export const initialRoomState: RoomState = {
  socketStatus: "connecting",
  code: null,
  status: "lobby",
  phase: "lobby",
  myPlayerId: null,
  players: [],
  minHumans: 4,
  capacity: 7,
  allowReplayUse: false,
  canStart: false,
  lastSeq: null,
  clockOffsetMs: 0,
  lastError: null,
  roundId: null,
  roundNumber: 0,
  totalRounds: 3,
  phaseEndsAtMs: null,
  topic: null,
  seats: [],
  mySeatId: null,
  hasAnswered: false,
  myAnswer: null,
  readyToVote: false,
  answers: [],
  messages: [],
  typingSeats: {},
  votesCast: 0,
  totalHumans: 0,
  myVoteTargetSeatId: null,
  reveal: null,
  gameOver: null,
};

function isStaleEvent(lastSeq: number | null, eventSeq: number): boolean {
  return lastSeq !== null && eventSeq <= lastSeq;
}

export function roomReducer(state: RoomState, action: RoomAction): RoomState {
  switch (action.type) {
    case "ws_status":
      return { ...state, socketStatus: action.status };

    case "room_snapshot": {
      const { payload, seq } = action;
      const isLobby = payload.phase === "lobby";
      return {
        ...state,
        socketStatus: "connected",
        code: payload.code,
        status: payload.status,
        phase: payload.phase,
        myPlayerId: payload.my_player_id,
        players: payload.roster,
        minHumans: payload.min_humans,
        capacity: payload.capacity,
        allowReplayUse: payload.allow_replay_use,
        canStart: payload.can_start,
        lastSeq: seq,
        clockOffsetMs: computeClockOffset(payload.server_time, action.localNowMs),
        lastError: null,
        roundId: isLobby ? null : (payload.round_id ?? state.roundId),
        roundNumber: isLobby ? 0 : (payload.round_number ?? state.roundNumber),
        totalRounds: payload.total_rounds ?? state.totalRounds,
        phaseEndsAtMs: isLobby ? null : (payload.ends_at ?? state.phaseEndsAtMs),
        topic: isLobby ? null : (payload.topic ?? state.topic),
        seats: isLobby ? [] : (payload.seats ?? state.seats),
        mySeatId: isLobby ? null : (payload.my_seat_id ?? state.mySeatId),
        hasAnswered: isLobby ? false : (payload.has_answered ?? false),
        myAnswer: isLobby ? null : (payload.my_answer ?? null),
        readyToVote: isLobby ? false : (payload.ready_to_vote ?? false),
        answers: isLobby ? [] : (payload.answers ?? []),
        messages: isLobby ? [] : (payload.messages ?? []),
        typingSeats: {},
        votesCast: isLobby ? 0 : (payload.votes_cast ?? 0),
        totalHumans: isLobby ? 0 : (payload.total_humans ?? 0),
        myVoteTargetSeatId: isLobby ? null : (payload.my_vote_target_seat_id ?? null),
        reveal: isLobby ? null : (payload.reveal ?? null),
        gameOver: isLobby ? null : (payload.game_over ?? null),
      };
    }

    case "player_joined": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      const incoming = action.payload.player;
      const exists = state.players.some((p) => p.id === incoming.id);
      const players = exists
        ? state.players.map((p) => (p.id === incoming.id ? incoming : p))
        : [...state.players, incoming];
      return {
        ...state,
        players,
        canStart: action.payload.can_start,
        lastSeq: action.seq,
      };
    }

    case "player_left": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      const newHostId = action.payload.new_host_id;
      return {
        ...state,
        players: state.players
          .filter((p) => p.id !== action.payload.player_id)
          .map((p) => (newHostId && p.id === newHostId ? { ...p, is_host: true } : p)),
        canStart: action.payload.can_start,
        lastSeq: action.seq,
      };
    }

    case "host_promoted": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      return {
        ...state,
        players: state.players.map((p) => ({
          ...p,
          is_host: p.id === action.payload.new_host_id,
        })),
        lastSeq: action.seq,
      };
    }

    case "presence": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      return {
        ...state,
        players: state.players.map((p) =>
          p.id === action.payload.player_id ? { ...p, connected: action.payload.connected } : p,
        ),
        canStart: action.payload.can_start,
        lastSeq: action.seq,
      };
    }

    case "phase_changed": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      const { payload } = action;
      if (payload.phase === "lobby") {
        return {
          ...state,
          status: "lobby",
          phase: "lobby",
          roundId: null,
          roundNumber: 0,
          totalRounds: payload.total_rounds,
          phaseEndsAtMs: null,
          clockOffsetMs: computeClockOffset(payload.server_time, action.localNowMs),
          topic: null,
          seats: [],
          mySeatId: null,
          hasAnswered: false,
          myAnswer: null,
          readyToVote: false,
          answers: [],
          messages: [],
          typingSeats: {},
          votesCast: 0,
          totalHumans: 0,
          myVoteTargetSeatId: null,
          reveal: null,
          gameOver: null,
          lastError: null,
          lastSeq: action.seq,
        };
      }
      const isNewRoundAnswer = payload.phase === "answer" && payload.round_id !== state.roundId;
      return {
        ...state,
        status: payload.phase === "done" ? "finished" : "in_progress",
        phase: payload.phase,
        roundId: payload.round_id,
        roundNumber: payload.round_number,
        totalRounds: payload.total_rounds,
        phaseEndsAtMs: payload.ends_at,
        clockOffsetMs: computeClockOffset(payload.server_time, action.localNowMs),
        topic: payload.topic,
        seats: payload.seats,
        hasAnswered: isNewRoundAnswer ? false : state.hasAnswered,
        myAnswer: isNewRoundAnswer ? null : state.myAnswer,
        readyToVote: isNewRoundAnswer ? false : state.readyToVote,
        answers: isNewRoundAnswer ? [] : state.answers,
        messages: isNewRoundAnswer ? [] : state.messages,
        typingSeats: {},
        votesCast: isNewRoundAnswer ? 0 : state.votesCast,
        myVoteTargetSeatId: isNewRoundAnswer ? null : state.myVoteTargetSeatId,
        reveal: isNewRoundAnswer ? null : state.reveal,
        lastSeq: action.seq,
      };
    }

    case "answers_revealed": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      return {
        ...state,
        answers: action.payload.answers,
        lastSeq: action.seq,
      };
    }

    case "chat_message": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      const msg = action.payload;
      const alreadyPresent = state.messages.some(
        (existing) =>
          existing.id === msg.id ||
          (msg.client_msg_id !== null && existing.client_msg_id === msg.client_msg_id),
      );
      const nextTyping = { ...state.typingSeats };
      delete nextTyping[msg.seat_id];
      return {
        ...state,
        messages: alreadyPresent ? state.messages : [...state.messages, msg],
        typingSeats: nextTyping,
        lastSeq: action.seq,
      };
    }

    case "vote_progress": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      return {
        ...state,
        votesCast: action.payload.votes_cast,
        totalHumans: action.payload.total_humans,
        lastSeq: action.seq,
      };
    }

    case "reveal": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      return {
        ...state,
        reveal: action.payload,
        players: mergePlayerScores(state.players, action.payload.leaderboard),
        lastSeq: action.seq,
      };
    }

    case "game_over": {
      if (isStaleEvent(state.lastSeq, action.seq)) {
        return state;
      }
      return {
        ...state,
        status: "finished",
        gameOver: action.payload,
        players: mergePlayerScores(state.players, action.payload.leaderboard),
        lastSeq: action.seq,
      };
    }

    case "typing": {
      const nowMs = action.nowMs ?? Date.now();
      const { seat_id, is_typing } = action.payload;
      if (seat_id === state.mySeatId) {
        return state;
      }
      const nextTyping = { ...state.typingSeats };
      if (is_typing) {
        nextTyping[seat_id] = nowMs + TYPING_TTL_MS;
      } else {
        delete nextTyping[seat_id];
      }
      return { ...state, typingSeats: nextTyping };
    }

    case "prune_typing": {
      const nowMs = action.nowMs ?? Date.now();
      const entries = Object.entries(state.typingSeats).filter(([, exp]) => exp > nowMs);
      if (entries.length === Object.keys(state.typingSeats).length) {
        return state;
      }
      return { ...state, typingSeats: Object.fromEntries(entries) };
    }

    case "answer_submitted_local":
      return {
        ...state,
        hasAnswered: true,
        myAnswer: action.text,
        lastError: null,
      };

    case "ready_to_vote_local":
      return {
        ...state,
        readyToVote: true,
        lastError: null,
      };

    case "vote_cast_local":
      return {
        ...state,
        myVoteTargetSeatId: action.targetSeatId,
        lastError: null,
      };

    case "server_error": {
      const rollbackAnswer =
        state.phase === "answer" &&
        (action.payload.code === "empty_text" ||
          action.payload.code === "text_too_long" ||
          action.payload.code === "invalid_payload");
      const rollbackVote =
        state.phase === "vote" &&
        (action.payload.code === "invalid_target" ||
          action.payload.code === "self_vote" ||
          action.payload.code === "invalid_phase");
      return {
        ...state,
        hasAnswered: rollbackAnswer ? false : state.hasAnswered,
        myVoteTargetSeatId: rollbackVote ? null : state.myVoteTargetSeatId,
        lastError: action.payload,
      };
    }

    case "clear_error":
      return { ...state, lastError: null };
  }
}
