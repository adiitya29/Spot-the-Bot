import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Lobby } from "../components/Lobby";
import { initialRoomState } from "../reducer";
import type { RoomState } from "../types";

function makeLobbyState(overrides: Partial<RoomState> = {}): RoomState {
  return {
    ...initialRoomState,
    socketStatus: "connected",
    code: "AB2C3D",
    myPlayerId: "p1",
    minHumans: 3,
    capacity: 7,
    players: [
      { id: "p1", nickname: "Alice", is_host: true, connected: true, score: 0 },
      { id: "p2", nickname: "Bob", is_host: false, connected: true, score: 0 },
    ],
    canStart: false,
    ...overrides,
  };
}

describe("Lobby component", () => {
  it("disables host Start Game button until canStart is true", () => {
    const onStartGame = vi.fn();
    render(
      <MemoryRouter>
        <Lobby
          room={makeLobbyState()}
          code="AB2C3D"
          onStartGame={onStartGame}
          onDismissError={vi.fn()}
        />
      </MemoryRouter>,
    );

    const startBtn = screen.getByRole("button", { name: "Start Game" });
    expect(startBtn).toBeDisabled();
    expect(screen.getByText(/Need 1 more connected player to start/)).toBeInTheDocument();
  });

  it("enables Start Game when enough connected players exist and fires callback", async () => {
    const user = userEvent.setup();
    const onStartGame = vi.fn();
    render(
      <MemoryRouter>
        <Lobby
          room={makeLobbyState({
            canStart: true,
            players: [
              { id: "p1", nickname: "Alice", is_host: true, connected: true, score: 0 },
              { id: "p2", nickname: "Bob", is_host: false, connected: true, score: 0 },
              { id: "p3", nickname: "Charlie", is_host: false, connected: false, score: 0 },
            ],
          })}
          code="AB2C3D"
          onStartGame={onStartGame}
          onDismissError={vi.fn()}
        />
      </MemoryRouter>,
    );

    const startBtn = screen.getByRole("button", { name: "Start Game" });
    expect(startBtn).toBeEnabled();
    expect(screen.getByText("Away")).toBeInTheDocument();

    await user.click(startBtn);
    expect(onStartGame).toHaveBeenCalledTimes(1);
  });

  it("shows waiting text instead of Start button for non-host players", () => {
    render(
      <MemoryRouter>
        <Lobby
          room={makeLobbyState({
            myPlayerId: "p2",
            canStart: true,
            players: [
              { id: "p1", nickname: "Alice", is_host: true, connected: true, score: 0 },
              { id: "p2", nickname: "Bob", is_host: false, connected: true, score: 0 },
              { id: "p3", nickname: "Charlie", is_host: false, connected: true, score: 0 },
            ],
          })}
          code="AB2C3D"
          onStartGame={vi.fn()}
          onDismissError={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("button", { name: "Start Game" })).not.toBeInTheDocument();
    expect(screen.getByText("Waiting for host to start the game...")).toBeInTheDocument();
  });
});
