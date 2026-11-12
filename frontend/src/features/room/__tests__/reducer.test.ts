import { describe, expect, it } from "vitest";
import { initialRoomState, roomReducer } from "../reducer";
import type { RoomSnapshotPayload } from "../types";

const baseSnapshot: RoomSnapshotPayload = {
  code: "AB2C3D",
  status: "lobby",
  phase: "lobby",
  min_humans: 3,
  capacity: 7,
  allow_replay_use: false,
  can_start: false,
  my_player_id: "p1",
  server_time: 10_500,
  roster: [{ id: "p1", nickname: "Alice", is_host: true, connected: true, score: 0 }],
};

describe("roomReducer", () => {
  it("replaces full state on room_snapshot and computes clock offset", () => {
    const state = roomReducer(initialRoomState, {
      type: "room_snapshot",
      seq: 1,
      payload: baseSnapshot,
      localNowMs: 10_000,
    });

    expect(state.socketStatus).toBe("connected");
    expect(state.code).toBe("AB2C3D");
    expect(state.players).toHaveLength(1);
    expect(state.lastSeq).toBe(1);
    expect(state.clockOffsetMs).toBe(500);
  });

  it("handles player_joined, presence, and player_left idempotently by seq", () => {
    let state = roomReducer(initialRoomState, {
      type: "room_snapshot",
      seq: 1,
      payload: baseSnapshot,
      localNowMs: 10_000,
    });

    state = roomReducer(state, {
      type: "player_joined",
      seq: 2,
      payload: {
        player: { id: "p2", nickname: "Bob", is_host: false, connected: true, score: 0 },
        can_start: false,
      },
    });
    expect(state.players).toHaveLength(2);
    expect(state.lastSeq).toBe(2);

    // Stale duplicate seq=2 is ignored
    const stale = roomReducer(state, {
      type: "player_left",
      seq: 2,
      payload: { player_id: "p2", nickname: "Bob", reason: "grace_expired", can_start: false },
    });
    expect(stale.players).toHaveLength(2);

    // Presence update marks Bob offline
    state = roomReducer(state, {
      type: "presence",
      seq: 3,
      payload: { player_id: "p2", connected: false, can_start: false },
    });
    expect(state.players[1].connected).toBe(false);

    // player_left removes Bob after grace expires
    state = roomReducer(state, {
      type: "player_left",
      seq: 4,
      payload: { player_id: "p2", nickname: "Bob", reason: "grace_expired", can_start: false },
    });
    expect(state.players).toHaveLength(1);
    expect(state.lastSeq).toBe(4);
  });
});
