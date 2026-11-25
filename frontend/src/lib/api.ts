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

function findFirstErrorDetail(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findFirstErrorDetail(item);
      if (found) return found;
    }
  } else if (typeof value === "object" && value !== null) {
    for (const nested of Object.values(value)) {
      const found = findFirstErrorDetail(nested);
      if (found) return found;
    }
  }
  return null;
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
    } else {
      const extracted = findFirstErrorDetail(body);
      if (extracted) {
        code = "validation_error";
        detail = extracted;
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

const DEFAULT_REQUEST_TIMEOUT_MS = 20_000;
const COLD_START_REQUEST_TIMEOUT_MS = 45_000;
const TRANSIENT_GATEWAY_STATUSES = new Set([502, 503, 504]);
const WARMUP_COOLDOWN_MS = 30_000;

let activeWarmup: Promise<void> | null = null;
let lastWarmupAt = 0;

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  retryOnGatewayError?: boolean;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const externalSignal = init.signal;
  const onExternalAbort = () => controller.abort(externalSignal?.reason);
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort(externalSignal.reason);
    } else {
      externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }
  }

  const timer = window.setTimeout(() => controller.abort("timeout"), timeoutMs);
  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } catch (err) {
    if (controller.signal.aborted && !externalSignal?.aborted) {
      throw new ApiError(
        408,
        "request_timeout",
        "Server took too long to respond (it may still be waking up). Please try again.",
      );
    }
    throw err;
  } finally {
    window.clearTimeout(timer);
    externalSignal?.removeEventListener("abort", onExternalAbort);
  }
}

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
    retryOnGatewayError = false,
    headers,
    ...init
  } = options;
  const maxAttempts = retryOnGatewayError ? 3 : 1;
  const deadline = Date.now() + timeoutMs;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const remainingMs = deadline - Date.now();
    if (remainingMs <= 0) {
      throw new ApiError(
        408,
        "request_timeout",
        "Server took too long to respond (it may still be waking up). Please try again.",
      );
    }

    let response: Response;
    try {
      response = await fetchWithTimeout(
        `${API_BASE}${path}`,
        {
          ...init,
          headers: {
            "Content-Type": "application/json",
            ...(headers ?? {}),
          },
        },
        remainingMs,
      );
    } catch (err) {
      // Retry brief connection drops only during pre-boot gateway recovery when time remains.
      const isTimeout = err instanceof ApiError && err.code === "request_timeout";
      if (
        !isTimeout &&
        retryOnGatewayError &&
        attempt < maxAttempts &&
        Date.now() + 2500 < deadline
      ) {
        await sleep(2000);
        continue;
      }
      throw err;
    }

    if (response.ok) {
      return (await response.json()) as T;
    }

    if (
      retryOnGatewayError &&
      TRANSIENT_GATEWAY_STATUSES.has(response.status) &&
      attempt < maxAttempts &&
      Date.now() + 2500 < deadline
    ) {
      await sleep(2000);
      continue;
    }

    throw await parseError(response);
  }

  throw new ApiError(503, "service_unavailable", "Server is still starting up. Please try again.");
}

export function warmupBackend(): Promise<void> {
  const now = Date.now();
  if (activeWarmup) {
    return activeWarmup;
  }
  if (now - lastWarmupAt < WARMUP_COOLDOWN_MS) {
    return Promise.resolve();
  }
  lastWarmupAt = now;
  activeWarmup = requestJson<HealthResponse>("/health/", {
    cache: "no-store",
    timeoutMs: COLD_START_REQUEST_TIMEOUT_MS,
  })
    .then(() => undefined)
    .catch(() => undefined)
    .finally(() => {
      activeWarmup = null;
    });
  return activeWarmup;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health/", { timeoutMs: COLD_START_REQUEST_TIMEOUT_MS });
}

export async function createRoom(
  nickname: string,
  config?: RoomConfigInput,
): Promise<CreateRoomResponse> {
  return requestJson<CreateRoomResponse>("/rooms/", {
    method: "POST",
    body: JSON.stringify(config ? { nickname, config } : { nickname }),
    timeoutMs: COLD_START_REQUEST_TIMEOUT_MS,
    retryOnGatewayError: true,
  });
}

export async function getRoom(code: string): Promise<RoomPublic> {
  const normalized = normalizeRoomCode(code);
  return requestJson<RoomPublic>(`/rooms/${encodeURIComponent(normalized)}/`, {
    timeoutMs: COLD_START_REQUEST_TIMEOUT_MS,
    retryOnGatewayError: true,
  });
}

export async function joinRoom(code: string, nickname: string): Promise<JoinRoomResponse> {
  const normalized = normalizeRoomCode(code);
  return requestJson<JoinRoomResponse>(`/rooms/${encodeURIComponent(normalized)}/join/`, {
    method: "POST",
    body: JSON.stringify({ nickname }),
    timeoutMs: COLD_START_REQUEST_TIMEOUT_MS,
    retryOnGatewayError: true,
  });
}

export function saveRoomSession(session: GuestSession): void {
  const key = `${SESSION_STORAGE_PREFIX}${normalizeRoomCode(session.roomCode)}`;
  const value = JSON.stringify(session);
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // Ignore storage quota errors
  }
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore storage quota errors
  }
}

export function loadRoomSession(code: string): GuestSession | null {
  const key = `${SESSION_STORAGE_PREFIX}${normalizeRoomCode(code)}`;
  let raw: string | null = null;
  try {
    raw = window.sessionStorage.getItem(key);
  } catch {
    // Ignore
  }
  if (!raw) {
    try {
      raw = window.localStorage.getItem(key);
    } catch {
      // Ignore
    }
  }
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
    // Ignore malformed storage entries
  }
  return null;
}

export function clearRoomSession(code: string): void {
  const key = `${SESSION_STORAGE_PREFIX}${normalizeRoomCode(code)}`;
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // Ignore
  }
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore
  }
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
