import type { RoomStatus } from "../../lib/api";

export interface LobbyPlayer {
  id: string;
  nickname: string;
  is_host: boolean;
  connected: boolean;
  score: number;
}

export type WsSocketStatus =
  "connecting" | "connected" | "reconnecting" | "evicted" | "auth_error" | "error";

export interface RoomSnapshotPayload {
  code: string;
  status: RoomStatus;
  phase: string;
  min_humans: number;
  capacity: number;
  allow_replay_use: boolean;
  can_start: boolean;
  my_player_id: string;
  server_time: number;
  roster: LobbyPlayer[];
}

export interface PlayerJoinedPayload {
  player: LobbyPlayer;
  can_start: boolean;
}

export interface PlayerLeftPayload {
  player_id: string;
  nickname: string;
  reason: string;
  can_start: boolean;
}

export interface PresencePayload {
  player_id: string;
  connected: boolean;
  can_start: boolean;
}

export interface ErrorPayload {
  code: string;
  message: string;
}

export interface WsEnvelope<T = unknown> {
  v: number;
  seq: number | null;
  type: string;
  payload: T;
}

export interface RoomState {
  socketStatus: WsSocketStatus;
  code: string | null;
  status: RoomStatus;
  phase: string;
  myPlayerId: string | null;
  players: LobbyPlayer[];
  minHumans: number;
  capacity: number;
  allowReplayUse: boolean;
  canStart: boolean;
  lastSeq: number | null;
  clockOffsetMs: number;
  lastError: ErrorPayload | null;
}

export type RoomAction =
  | { type: "ws_status"; status: WsSocketStatus }
  | { type: "room_snapshot"; seq: number | null; payload: RoomSnapshotPayload; localNowMs?: number }
  | { type: "player_joined"; seq: number; payload: PlayerJoinedPayload }
  | { type: "player_left"; seq: number; payload: PlayerLeftPayload }
  | { type: "presence"; seq: number; payload: PresencePayload }
  | { type: "server_error"; payload: ErrorPayload }
  | { type: "clear_error" };
