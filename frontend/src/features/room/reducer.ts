import { computeClockOffset } from "../../lib/clockSync";
import type { RoomAction, RoomState } from "./types";

const TYPING_TTL_MS = 4000;

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
      return {
        ...state,
        players: state.players.filter((p) => p.id !== action.payload.player_id),
        canStart: action.payload.can_start,
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

    case "server_error": {
      const rollbackAnswer =
        state.phase === "answer" &&
        (action.payload.code === "empty_text" ||
          action.payload.code === "text_too_long" ||
          action.payload.code === "invalid_payload");
      return {
        ...state,
        hasAnswered: rollbackAnswer ? false : state.hasAnswered,
        lastError: action.payload,
      };
    }

    case "clear_error":
      return { ...state, lastError: null };
  }
}
