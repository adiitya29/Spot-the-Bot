export interface RoomState {
  status: "idle" | "connected" | "error";
  lastEcho: string | null;
}

export type RoomEvent =
  { type: "ws_connected" } | { type: "ws_echo"; payload: string } | { type: "ws_error" };

export const initialRoomState: RoomState = {
  status: "idle",
  lastEcho: null,
};

export function roomReducer(state: RoomState, event: RoomEvent): RoomState {
  switch (event.type) {
    case "ws_connected":
      return { ...state, status: "connected" };
    case "ws_echo":
      return { ...state, lastEcho: event.payload };
    case "ws_error":
      return { ...state, status: "error" };
  }
}
