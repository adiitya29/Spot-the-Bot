import { useCallback, useEffect, useRef } from "react";
import { BACKEND_URL, PROTOCOL_VERSION, normalizeRoomCode } from "../../lib/constants";
import { useRoomStore } from "./roomStore";
import type {
  AnswersRevealedPayload,
  ChatMessage,
  ErrorPayload,
  GameOverPayload,
  HostPromotedPayload,
  PhaseChangedPayload,
  PlayerJoinedPayload,
  PlayerLeftPayload,
  PresencePayload,
  RevealPayload,
  RoomSnapshotPayload,
  TypingPayload,
  VoteProgressPayload,
  WsEnvelope,
} from "./types";

const PING_INTERVAL_MS = 20_000;
const MAX_BACKOFF_MS = 15_000;
const CLOSE_REPLACED = 4001;
const CLOSE_AUTH_FAILED = 4401;
const CLOSE_FORBIDDEN = 4403;
const CLOSE_SEQ_GAP = 4000;

function nextClientId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function computeReconnectDelay(attempt: number, rng: () => number = Math.random): number {
  const base = Math.min(MAX_BACKOFF_MS, 500 * 2 ** attempt);
  const jitter = Math.floor(rng() * 400);
  return Math.min(MAX_BACKOFF_MS, base + jitter);
}

export function useRoomSocket(roomCode: string, token: string | null) {
  const socketRef = useRef<WebSocket | null>(null);
  const dispatch = useRoomStore((s) => s.dispatch);
  const reset = useRoomStore((s) => s.reset);
  const normalizedCode = normalizeRoomCode(roomCode);

  useEffect(() => {
    if (!normalizedCode || !token) {
      return;
    }

    let disposed = false;
    let attempt = 0;
    let pingTimer: number | null = null;
    let reconnectTimer: number | null = null;

    const clearTimers = () => {
      if (pingTimer !== null) {
        window.clearInterval(pingTimer);
        pingTimer = null;
      }
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const connect = () => {
      if (disposed) {
        return;
      }
      dispatch({ type: "ws_status", status: attempt === 0 ? "connecting" : "reconnecting" });

      let wsBaseUrl = "";
      if (BACKEND_URL) {
        wsBaseUrl = BACKEND_URL.replace(/^http/, "ws");
      } else {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        wsBaseUrl = `${protocol}//${window.location.host}`;
      }
      const url = `${wsBaseUrl}/ws/rooms/${encodeURIComponent(normalizedCode)}/?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        attempt = 0;
        pingTimer = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(
              JSON.stringify({
                v: PROTOCOL_VERSION,
                id: nextClientId(),
                type: "ping",
                payload: {},
              }),
            );
          }
        }, PING_INTERVAL_MS);
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        let frame: WsEnvelope;
        try {
          frame = JSON.parse(event.data) as WsEnvelope;
        } catch {
          return;
        }

        if (frame.type === "pong") {
          return;
        }

        if (frame.type === "typing") {
          dispatch({
            type: "typing",
            payload: frame.payload as TypingPayload,
          });
          return;
        }

        if (frame.type === "room_snapshot") {
          dispatch({
            type: "room_snapshot",
            seq: frame.seq,
            payload: frame.payload as RoomSnapshotPayload,
          });
          return;
        }

        if (frame.type === "error") {
          dispatch({
            type: "server_error",
            payload: frame.payload as ErrorPayload,
          });
          return;
        }

        const currentLastSeq = useRoomStore.getState().lastSeq;
        if (typeof frame.seq === "number" && currentLastSeq !== null) {
          if (frame.seq <= currentLastSeq) {
            return;
          }
        }

        if (typeof frame.seq !== "number") {
          return;
        }

        switch (frame.type) {
          case "player_joined":
            dispatch({
              type: "player_joined",
              seq: frame.seq,
              payload: frame.payload as PlayerJoinedPayload,
            });
            break;
          case "player_left":
            dispatch({
              type: "player_left",
              seq: frame.seq,
              payload: frame.payload as PlayerLeftPayload,
            });
            break;
          case "host_promoted":
            dispatch({
              type: "host_promoted",
              seq: frame.seq,
              payload: frame.payload as HostPromotedPayload,
            });
            break;
          case "presence":
            dispatch({
              type: "presence",
              seq: frame.seq,
              payload: frame.payload as PresencePayload,
            });
            break;
          case "phase_changed":
            dispatch({
              type: "phase_changed",
              seq: frame.seq,
              payload: frame.payload as PhaseChangedPayload,
            });
            break;
          case "answers_revealed":
            dispatch({
              type: "answers_revealed",
              seq: frame.seq,
              payload: frame.payload as AnswersRevealedPayload,
            });
            break;
          case "chat_message":
            dispatch({
              type: "chat_message",
              seq: frame.seq,
              payload: frame.payload as ChatMessage,
            });
            break;
          case "vote_progress":
            dispatch({
              type: "vote_progress",
              seq: frame.seq,
              payload: frame.payload as VoteProgressPayload,
            });
            break;
          case "reveal":
            dispatch({
              type: "reveal",
              seq: frame.seq,
              payload: frame.payload as RevealPayload,
            });
            break;
          case "game_over":
            dispatch({
              type: "game_over",
              seq: frame.seq,
              payload: frame.payload as GameOverPayload,
            });
            break;
        }
      };

      ws.onclose = (event: CloseEvent) => {
        if (pingTimer !== null) {
          window.clearInterval(pingTimer);
          pingTimer = null;
        }
        if (disposed) {
          return;
        }
        if (event.code === CLOSE_REPLACED) {
          dispatch({ type: "ws_status", status: "evicted" });
          return;
        }
        if (event.code === CLOSE_AUTH_FAILED || event.code === CLOSE_FORBIDDEN) {
          dispatch({ type: "ws_status", status: "auth_error" });
          return;
        }

        dispatch({ type: "ws_status", status: "reconnecting" });
        const delayMs = event.code === CLOSE_SEQ_GAP ? 50 : computeReconnectDelay(attempt);
        attempt += 1;
        reconnectTimer = window.setTimeout(connect, delayMs);
      };

      ws.onerror = () => {
        if (!disposed) {
          dispatch({ type: "ws_status", status: "reconnecting" });
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      clearTimers();
      socketRef.current?.close(1000, "unmount");
      socketRef.current = null;
      reset();
    };
  }, [dispatch, normalizedCode, reset, token]);

  const sendCommand = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    const ws = socketRef.current;
    if (ws?.readyState !== WebSocket.OPEN) {
      return false;
    }
    ws.send(
      JSON.stringify({
        v: PROTOCOL_VERSION,
        id: nextClientId(),
        type,
        payload,
      }),
    );
    return true;
  }, []);

  return { sendCommand };
}
