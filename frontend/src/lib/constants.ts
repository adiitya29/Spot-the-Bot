export const API_BASE = "/api";
export const WS_ECHO_PATH = "/ws/echo/";
export const PROTOCOL_VERSION = 1;

export const ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
export const ROOM_CODE_LENGTH = 6;
export const NICKNAME_MIN_LENGTH = 2;
export const NICKNAME_MAX_LENGTH = 20;
export const MAX_GAME_TEXT_LENGTH = 280;
export const SESSION_STORAGE_PREFIX = "stb_session_";

export interface SeatColorTheme {
  dot: string;
  badge: string;
  text: string;
}

export const SEAT_COLOR_THEMES: readonly SeatColorTheme[] = [
  { dot: "bg-teal-400", badge: "bg-teal-500/15 border-teal-500/40", text: "text-teal-300" },
  { dot: "bg-amber-400", badge: "bg-amber-500/15 border-amber-500/40", text: "text-amber-300" },
  { dot: "bg-rose-400", badge: "bg-rose-500/15 border-rose-500/40", text: "text-rose-300" },
  { dot: "bg-sky-400", badge: "bg-sky-500/15 border-sky-500/40", text: "text-sky-300" },
  {
    dot: "bg-emerald-400",
    badge: "bg-emerald-500/15 border-emerald-500/40",
    text: "text-emerald-300",
  },
  {
    dot: "bg-violet-400",
    badge: "bg-violet-500/15 border-violet-500/40",
    text: "text-violet-300",
  },
  {
    dot: "bg-orange-400",
    badge: "bg-orange-500/15 border-orange-500/40",
    text: "text-orange-300",
  },
  { dot: "bg-cyan-400", badge: "bg-cyan-500/15 border-cyan-500/40", text: "text-cyan-300" },
  { dot: "bg-pink-400", badge: "bg-pink-500/15 border-pink-500/40", text: "text-pink-300" },
  { dot: "bg-lime-400", badge: "bg-lime-500/15 border-lime-500/40", text: "text-lime-300" },
] as const;

export function getSeatColorTheme(colorIndex: number): SeatColorTheme {
  const safeIndex =
    ((colorIndex % SEAT_COLOR_THEMES.length) + SEAT_COLOR_THEMES.length) % SEAT_COLOR_THEMES.length;
  return SEAT_COLOR_THEMES[safeIndex] ?? SEAT_COLOR_THEMES[0]!;
}

export function normalizeRoomCode(raw: string): string {
  return raw.trim().toUpperCase();
}
