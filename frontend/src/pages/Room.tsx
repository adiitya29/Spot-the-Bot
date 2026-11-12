import { Navigate, useParams } from "react-router-dom";
import { Lobby } from "../features/room/components/Lobby";
import { useRoomStore } from "../features/room/roomStore";
import { useRoomSocket } from "../features/room/useRoomSocket";
import { loadRoomSession } from "../lib/api";
import { normalizeRoomCode } from "../lib/constants";

export function Room() {
  const { code: rawCode = "" } = useParams();
  const code = normalizeRoomCode(rawCode);
  const session = loadRoomSession(code);

  const roomState = useRoomStore();
  const { sendCommand } = useRoomSocket(code, session?.token ?? null);

  if (!session) {
    return <Navigate to={`/join/${code}`} replace />;
  }

  return (
    <Lobby
      room={roomState}
      code={code}
      onStartGame={() => {
        sendCommand("start_game", {});
      }}
      onDismissError={() => {
        roomState.dispatch({ type: "clear_error" });
      }}
    />
  );
}
