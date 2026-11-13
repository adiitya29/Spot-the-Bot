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
  votes_cast?: number;
  total_humans?: number;
  my_vote_target_seat_id?: string | null;
  reveal?: RevealPayload | null;
  game_over?: GameOverPayload | null;
}

export interface VoteProgressPayload {
  round_id: string;
  votes_cast: number;
  total_humans: number;
}

export interface RevealTallyEntry {
  seat_id: string;
  alias: string;
  color_index: number;
  is_bot: boolean;
  player_id: string | null;
  nickname: string;
  votes_received: number;
  voter_seat_ids: string[];
  voted_target_seat_id: string | null;
  round_points: number;
  total_score: number | null;
}

export interface LeaderboardEntry {
  rank?: number;
  player_id: string;
  nickname: string;
  is_host: boolean;
  connected: boolean;
  score: number;
  round_points?: number;
}

export interface RevealPayload {
  round_id: string;
  round_number: number;
  total_rounds: number;
  bot_seat_id: string;
  bot_alias: string;
  votes_for_bot: number;
  human_voters: number;
  bot_fooled: boolean;
  tally: RevealTallyEntry[];
  leaderboard: LeaderboardEntry[];
}

export interface RoundSummaryEntry {
  round_number: number;
  topic_text: string;
  topic_category: string;
  bot_alias: string;
  votes_for_bot: number;
  human_voters: number;
  bot_fooled: boolean;
}

export interface GameOverPayload {
  game_index: number;
  total_rounds: number;
  bot_fooled_count: number;
  leaderboard: LeaderboardEntry[];
  rounds_summary: RoundSummaryEntry[];
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
  new_host_id?: string | null;
}

export interface HostPromotedPayload {
  new_host_id: string;
  previous_host_id?: string | null;
}

export interface PresencePayload {
  player_id: string;
  connected: boolean;
  can_start: boolean;
}

export interface PhaseChangedPayload {
  round_id: string | null;
  game_index: number;
  round_number: number;
  total_rounds: number;
  phase: string;
  ends_at: number | null;
  server_time: number;
  topic: TopicInfo | null;
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
  votesCast: number;
  totalHumans: number;
  myVoteTargetSeatId: string | null;
  reveal: RevealPayload | null;
  gameOver: GameOverPayload | null;
}

export type RoomAction =
  | { type: "ws_status"; status: WsSocketStatus }
  | { type: "room_snapshot"; seq: number | null; payload: RoomSnapshotPayload; localNowMs?: number }
  | { type: "player_joined"; seq: number; payload: PlayerJoinedPayload }
  | { type: "player_left"; seq: number; payload: PlayerLeftPayload }
  | { type: "host_promoted"; seq: number; payload: HostPromotedPayload }
  | { type: "presence"; seq: number; payload: PresencePayload }
  | { type: "phase_changed"; seq: number; payload: PhaseChangedPayload; localNowMs?: number }
  | { type: "answers_revealed"; seq: number; payload: AnswersRevealedPayload }
  | { type: "chat_message"; seq: number; payload: ChatMessage }
  | { type: "vote_progress"; seq: number; payload: VoteProgressPayload }
  | { type: "reveal"; seq: number; payload: RevealPayload }
  | { type: "game_over"; seq: number; payload: GameOverPayload }
  | { type: "typing"; payload: TypingPayload; nowMs?: number }
  | { type: "prune_typing"; nowMs?: number }
  | { type: "answer_submitted_local"; text: string }
  | { type: "ready_to_vote_local" }
  | { type: "vote_cast_local"; targetSeatId: string }
  | { type: "server_error"; payload: ErrorPayload }
  | { type: "clear_error" };
