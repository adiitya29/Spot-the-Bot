import type { RoomStatus } from "../../lib/api";

export interface LobbyPlayer {
  id: string;
  nickname: string;
  is_host: boolean;
  connected: boolean;
  score: number;
}

export interface TopicInfo {
  id: number;
  text: string;
  category: string;
}

export interface RoundSeat {
  seat_id: string;
  alias: string;
  color_index: number;
}

export interface RoundAnswer {
  seat_id: string;
  alias: string;
  color_index: number;
  text: string;
}

export interface ChatMessage {
  id: number;
  round_id: string;
  seat_id: string;
  alias: string;
  color_index: number;
  text: string;
  client_msg_id: string | null;
  created_at: number;
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
  round_id?: string;
  round_number?: number;
  total_rounds?: number;
  ends_at?: number;
  topic?: TopicInfo;
  seats?: RoundSeat[];
  my_seat_id?: string | null;
  has_answered?: boolean;
  my_answer?: string | null;
  ready_to_vote?: boolean;
  answers?: RoundAnswer[];
  messages?: ChatMessage[];
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

export interface PhaseChangedPayload {
  round_id: string;
  game_index: number;
  round_number: number;
  total_rounds: number;
  phase: string;
  ends_at: number;
  server_time: number;
  topic: TopicInfo;
  seats: RoundSeat[];
}

export interface AnswersRevealedPayload {
  round_id: string;
  answers: RoundAnswer[];
}

export interface TypingPayload {
  seat_id: string;
  is_typing: boolean;
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
  roundId: string | null;
  roundNumber: number;
  totalRounds: number;
  phaseEndsAtMs: number | null;
  topic: TopicInfo | null;
  seats: RoundSeat[];
  mySeatId: string | null;
  hasAnswered: boolean;
  myAnswer: string | null;
  readyToVote: boolean;
  answers: RoundAnswer[];
  messages: ChatMessage[];
  typingSeats: Record<string, number>;
}

export type RoomAction =
  | { type: "ws_status"; status: WsSocketStatus }
  | { type: "room_snapshot"; seq: number | null; payload: RoomSnapshotPayload; localNowMs?: number }
  | { type: "player_joined"; seq: number; payload: PlayerJoinedPayload }
  | { type: "player_left"; seq: number; payload: PlayerLeftPayload }
  | { type: "presence"; seq: number; payload: PresencePayload }
  | { type: "phase_changed"; seq: number; payload: PhaseChangedPayload; localNowMs?: number }
  | { type: "answers_revealed"; seq: number; payload: AnswersRevealedPayload }
  | { type: "chat_message"; seq: number; payload: ChatMessage }
  | { type: "typing"; payload: TypingPayload; nowMs?: number }
  | { type: "prune_typing"; nowMs?: number }
  | { type: "answer_submitted_local"; text: string }
  | { type: "ready_to_vote_local" }
  | { type: "server_error"; payload: ErrorPayload }
  | { type: "clear_error" };
