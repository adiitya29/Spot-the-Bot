import { useCallback, useEffect, useRef } from "react";
import { WS_ECHO_PATH } from "../../lib/constants";
import { useRoomStore } from "./roomStore";

interface EchoFrame {
  v: number;
  type: string;
  payload: unknown;
}

export function useRoomSocket() {
  const socketRef = useRef<WebSocket | null>(null);
  const dispatch = useRoomStore((s) => s.dispatch);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}${WS_ECHO_PATH}`;
    const ws = new WebSocket(url);
    socketRef.current = ws;

    ws.onopen = () => {
      dispatch({ type: "ws_connected" });
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const frame = JSON.parse(event.data) as EchoFrame;
        if (frame.type === "echo") {
          dispatch({ type: "ws_echo", payload: JSON.stringify(frame.payload) });
        }
      } catch {
        dispatch({ type: "ws_error" });
      }
    };

    ws.onerror = () => {
      dispatch({ type: "ws_error" });
    };

    return () => {
      ws.close();
      socketRef.current = null;
    };
  }, [dispatch]);

  const sendEcho = useCallback((message: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ message }));
    }
  }, []);

  return { sendEcho };
}
