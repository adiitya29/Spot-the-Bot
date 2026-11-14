import { API_BASE, SESSION_STORAGE_PREFIX, normalizeRoomCode } from "./constants";

export interface HealthResponse {
  status: string;
}

export type RoomStatus = "lobby" | "in_progress" | "finished" | "abandoned";

export interface PhaseDurations {
  answer: number;
  chat: number;
  vote: number;
  reveal: number;
}

export interface RoomConfig {
  rounds: number;
  min_humans: number;
  allow_replay_use: boolean;
  phase_durations: PhaseDurations;
}

export interface RoomConfigInput {
  rounds?: number;
  min_humans?: number;
  allow_replay_use?: boolean;
  phase_durations?: Partial<PhaseDurations>;
}

export interface RoomPublic {
  code: string;
  status: RoomStatus;
  human_count: number;
  capacity: number;
  min_humans: number;
  allow_replay_use: boolean;
  config: RoomConfig;
}

export interface PlayerPublic {
  id: string;
  nickname: string;
  is_host: boolean;
  connected: boolean;
  score: number;
  joined_at: string;
}

export interface CreateRoomResponse {
  code: string;
  room: RoomPublic;
  player: PlayerPublic;
  player_token: string;
}

export interface JoinRoomResponse {
  room: RoomPublic;
  player: PlayerPublic;
  player_token: string;
}

export interface GuestSession {
  roomCode: string;
  playerId: string;
  nickname: string;
  token: string;
  isHost: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let code = "request_failed";
  let detail = `Request failed (${response.status})`;
  try {
    const body = (await response.json()) as Record<string, unknown>;
    if (typeof body.code === "string") {
      code = body.code;
    }
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.nickname) && typeof body.nickname[0] === "string") {
      code = "validation_error";
      detail = body.nickname[0];
    } else if (typeof body === "object" && body !== null) {
      const firstValue = Object.values(body)[0];
      if (Array.isArray(firstValue) && typeof firstValue[0] === "string") {
        code = "validation_error";
        detail = firstValue[0];
      }
    }
  } catch {
    // Fallback to HTTP status text when body is not JSON
  }
  if (response.status === 429) {
    code = "rate_limited";
    detail = "Too many requests from your connection. Please wait and try again.";
  }
  return new ApiError(response.status, code, detail);
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health/");
}

export async function createRoom(
  nickname: string,
  config?: RoomConfigInput,
): Promise<CreateRoomResponse> {
  return requestJson<CreateRoomResponse>("/rooms/", {
    method: "POST",
    body: JSON.stringify(config ? { nickname, config } : { nickname }),
  });
}

export async function getRoom(code: string): Promise<RoomPublic> {
  const normalized = normalizeRoomCode(code);
  return requestJson<RoomPublic>(`/rooms/${encodeURIComponent(normalized)}/`);
}

export async function joinRoom(code: string, nickname: string): Promise<JoinRoomResponse> {
  const normalized = normalizeRoomCode(code);
  return requestJson<JoinRoomResponse>(`/rooms/${encodeURIComponent(normalized)}/join/`, {
    method: "POST",
    body: JSON.stringify({ nickname }),
  });
}

export function saveRoomSession(session: GuestSession): void {
  const key = `${SESSION_STORAGE_PREFIX}${normalizeRoomCode(session.roomCode)}`;
  window.localStorage.setItem(key, JSON.stringify(session));
}

export function loadRoomSession(code: string): GuestSession | null {
  const key = `${SESSION_STORAGE_PREFIX}${normalizeRoomCode(code)}`;
  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<GuestSession>;
    if (
      typeof parsed.token === "string" &&
      typeof parsed.playerId === "string" &&
      typeof parsed.nickname === "string" &&
      typeof parsed.roomCode === "string"
    ) {
      return {
        roomCode: normalizeRoomCode(parsed.roomCode),
        playerId: parsed.playerId,
        nickname: parsed.nickname,
        token: parsed.token,
        isHost: Boolean(parsed.isHost),
      };
    }
  } catch {
    // Ignore malformed localStorage entries
  }
  return null;
}

export function clearRoomSession(code: string): void {
  const key = `${SESSION_STORAGE_PREFIX}${normalizeRoomCode(code)}`;
  window.localStorage.removeItem(key);
}

export interface ReplayListItem {
  id: string;
  room_code: string;
  topic_category: string;
  topic_text: string;
  human_guesses_count: number;
  correct_guesses_count: number;
  solo_accuracy_rate: number;
  solo_bot_fooled_rate: number;
  created_at: string;
}

export interface ReplayTranscriptParticipant {
  seat_id: string;
  alias: string;
  color_index: number;
  nickname?: string;
}

export interface ReplayTranscriptAnswer {
  seat_id: string;
  alias: string;
  text: string;
  submitted_at?: string;
}

export interface ReplayTranscriptMessage {
  id: string;
  seat_id: string;
  alias: string;
  text: string;
  latency_ms: number;
  timestamp_ms?: number;
}

export interface ReplayDetail extends ReplayListItem {
  transcript: {
    participants: ReplayTranscriptParticipant[];
    answers: ReplayTranscriptAnswer[];
    messages: ReplayTranscriptMessage[];
    outcome?: {
      votes_on_bot: number;
      human_voters: number;
      bot_fooled: boolean;
    };
  };
}

export interface SoloGuessResponse {
  correct: boolean;
  guessed_alias: string;
  bot_alias: string;
  human_guesses_count: number;
  correct_guesses_count: number;
  solo_accuracy_rate: number;
  solo_bot_fooled_rate: number;
  explanation: string;
}

export interface BotGlobalStats {
  live_games: {
    total_rounds: number;
    bot_fooled_count: number;
    bot_fooled_rate: number;
    total_votes_on_bot: number;
    total_human_voters: number;
    human_accuracy_rate: number;
  };
  solo_replays: {
    total_replays_available: number;
    total_guesses: number;
    correct_guesses: number;
    fooled_guesses: number;
    bot_fooled_rate: number;
  };
  overall: {
    total_encounters: number;
    total_fooled: number;
    bot_fooled_rate: number;
  };
}

export async function getReplays(): Promise<ReplayListItem[]> {
  return requestJson<ReplayListItem[]>("/replays/");
}

export async function getReplay(id: string): Promise<ReplayDetail> {
  return requestJson<ReplayDetail>(`/replays/${encodeURIComponent(id)}/`);
}

export async function submitSoloGuess(id: string, alias: string): Promise<SoloGuessResponse> {
  return requestJson<SoloGuessResponse>(`/replays/${encodeURIComponent(id)}/guess/`, {
    method: "POST",
    body: JSON.stringify({ alias }),
  });
}

export async function getBotStats(): Promise<BotGlobalStats> {
  return requestJson<BotGlobalStats>("/stats/bot/");
}
