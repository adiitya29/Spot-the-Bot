import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRoomStore } from "../../features/room/roomStore";
import { loadRoomSession } from "../../lib/api";
import { Join } from "../Join";
import { Landing } from "../Landing";
import { Room } from "../Room";

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  readyState = MockWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
  });
}

function renderWithRouter(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/join/:code" element={<Join />} />
          <Route path="/r/:code" element={<Room />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Landing and Join flows", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useRoomStore.getState().reset();
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a room, stores token in localStorage, and navigates to /r/:code", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        code: "AB2C3D",
        player_token: "signed-host-token",
        player: {
          id: "p-host",
          nickname: "Alice",
          is_host: true,
          connected: false,
          score: 0,
          joined_at: "2026-11-12T00:00:00Z",
        },
        room: {
          code: "AB2C3D",
          status: "lobby",
          human_count: 1,
          capacity: 7,
          min_humans: 3,
          allow_replay_use: true,
          config: {
            rounds: 3,
            min_humans: 3,
            allow_replay_use: true,
            phase_durations: { answer: 45, chat: 120, vote: 30, reveal: 12 },
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithRouter("/");
    await user.type(screen.getByLabelText("Your Nickname"), "Alice");
    await user.click(screen.getByRole("button", { name: "Customize room settings" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Create Room" }));

    expect(await screen.findByText("ROOM AB2C3D")).toBeInTheDocument();
    expect(screen.getByText("Game Lobby")).toBeInTheDocument();
    expect(loadRoomSession("AB2C3D")).toEqual({
      roomCode: "AB2C3D",
      playerId: "p-host",
      nickname: "Alice",
      token: "signed-host-token",
      isHost: true,
    });
  });

  it("joins a room via /join/:code and stores guest token", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          code: "AB2C3D",
          status: "lobby",
          human_count: 2,
          capacity: 7,
          min_humans: 3,
          allow_replay_use: true,
          config: {
            rounds: 3,
            min_humans: 3,
            allow_replay_use: true,
            phase_durations: { answer: 45, chat: 120, vote: 30, reveal: 12 },
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          player_token: "signed-guest-token",
          player: {
            id: "p-bob",
            nickname: "Bob",
            is_host: false,
            connected: false,
            score: 0,
            joined_at: "2026-11-12T00:01:00Z",
          },
          room: {
            code: "AB2C3D",
            status: "lobby",
            human_count: 3,
            capacity: 7,
            min_humans: 3,
            allow_replay_use: true,
            config: {
              rounds: 3,
              min_humans: 3,
              allow_replay_use: true,
              phase_durations: { answer: 45, chat: 120, vote: 30, reveal: 12 },
            },
          },
        }),
      });
    vi.stubGlobal("fetch", fetchMock);

    renderWithRouter("/join/ab2c3d");
    expect(await screen.findByText(/2 \/ 7 humans/)).toBeInTheDocument();
    expect(screen.getByText(/Host enabled anonymized public replays/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Choose Nickname"), "Bob");
    await user.click(screen.getByRole("button", { name: "Join Lobby" }));

    await waitFor(() => {
      expect(screen.getByText("Game Lobby")).toBeInTheDocument();
    });
    expect(loadRoomSession("AB2C3D")?.token).toBe("signed-guest-token");
  });

  it("displays 409 duplicate nickname error inline", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          code: "AB2C3D",
          status: "lobby",
          human_count: 2,
          capacity: 7,
          min_humans: 3,
          allow_replay_use: false,
          config: {
            rounds: 3,
            min_humans: 3,
            allow_replay_use: false,
            phase_durations: { answer: 45, chat: 120, vote: 30, reveal: 12 },
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({
          code: "nickname_taken",
          detail: "That nickname is already taken in this room.",
        }),
      });
    vi.stubGlobal("fetch", fetchMock);

    renderWithRouter("/join/AB2C3D");
    await screen.findByLabelText("Choose Nickname");
    await user.type(screen.getByLabelText("Choose Nickname"), "Alice");
    await user.click(screen.getByRole("button", { name: "Join Lobby" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That nickname is already taken in this room.",
    );
  });

  it("blocks joining started rooms", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          code: "XY7Z8K",
          status: "in_progress",
          human_count: 4,
          capacity: 7,
          min_humans: 4,
          allow_replay_use: false,
          config: {
            rounds: 3,
            min_humans: 4,
            allow_replay_use: false,
            phase_durations: { answer: 45, chat: 120, vote: 30, reveal: 12 },
          },
        }),
      }),
    );

    renderWithRouter("/join/XY7Z8K");
    expect(await screen.findByRole("alert")).toHaveTextContent("This game has already started.");
  });
});
