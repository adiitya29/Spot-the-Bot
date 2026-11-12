import { computeClockOffset } from "../../lib/clockSync";
import type { RoomAction, RoomState } from "./types";

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

    case "server_error":
      return { ...state, lastError: action.payload };

    case "clear_error":
      return { ...state, lastError: null };
  }
}
