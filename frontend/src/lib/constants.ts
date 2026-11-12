export const API_BASE = "/api";
export const WS_ECHO_PATH = "/ws/echo/";
export const PROTOCOL_VERSION = 1;

export const ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
export const ROOM_CODE_LENGTH = 6;
export const NICKNAME_MIN_LENGTH = 2;
export const NICKNAME_MAX_LENGTH = 20;
export const SESSION_STORAGE_PREFIX = "stb_session_";

export function normalizeRoomCode(raw: string): string {
  return raw.trim().toUpperCase();
}
