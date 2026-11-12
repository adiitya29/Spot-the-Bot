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

  it("handles Phase 3 phase_changed, answers_revealed, chat_message dedupe, and typing", () => {
    let state = roomReducer(initialRoomState, {
      type: "room_snapshot",
      seq: 1,
      payload: {
        ...baseSnapshot,
        status: "in_progress",
        phase: "answer",
        round_id: "r1",
        round_number: 1,
        total_rounds: 3,
        ends_at: 55_000,
        topic: { id: 1, text: "Weird snack combos?", category: "funny" },
        seats: [
          { seat_id: "s1", alias: "Teal Otter", color_index: 0 },
          { seat_id: "s2", alias: "Coral Fox", color_index: 1 },
        ],
        my_seat_id: "s1",
      },
      localNowMs: 10_000,
    });

    expect(state.mySeatId).toBe("s1");
    expect(state.topic?.text).toBe("Weird snack combos?");

    state = roomReducer(state, {
      type: "answers_revealed",
      seq: 2,
      payload: {
        round_id: "r1",
        answers: [
          { seat_id: "s1", alias: "Teal Otter", color_index: 0, text: "Fries in shake" },
          { seat_id: "s2", alias: "Coral Fox", color_index: 1, text: "Hot sauce on apples" },
        ],
      },
    });
    expect(state.answers).toHaveLength(2);

    state = roomReducer(state, {
      type: "phase_changed",
      seq: 3,
      payload: {
        round_id: "r1",
        game_index: 1,
        round_number: 1,
        total_rounds: 3,
        phase: "chat",
        ends_at: 170_000,
        server_time: 50_200,
        topic: { id: 1, text: "Weird snack combos?", category: "funny" },
        seats: [
          { seat_id: "s1", alias: "Teal Otter", color_index: 0 },
          { seat_id: "s2", alias: "Coral Fox", color_index: 1 },
        ],
      },
      localNowMs: 50_000,
    });
    expect(state.phase).toBe("chat");
    expect(state.clockOffsetMs).toBe(200);

    // Typing from other seat expires cleanly
    state = roomReducer(state, {
      type: "typing",
      payload: { seat_id: "s2", is_typing: true },
      nowMs: 51_000,
    });
    expect(Object.keys(state.typingSeats)).toEqual(["s2"]);

    // Receiving chat_message appends once (deduped by client_msg_id) and clears typing indicator
    const chatPayload = {
      id: 99,
      round_id: "r1",
      seat_id: "s2",
      alias: "Coral Fox",
      color_index: 1,
      text: "Apples and hot sauce is gourmet",
      client_msg_id: "uuid-msg-1",
      created_at: 52_000,
    };
    state = roomReducer(state, { type: "chat_message", seq: 4, payload: chatPayload });
    state = roomReducer(state, { type: "chat_message", seq: 5, payload: chatPayload });
    expect(state.messages).toHaveLength(1);
    expect(Object.keys(state.typingSeats)).toHaveLength(0);
  });
});
