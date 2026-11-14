import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import { Replays } from "../Replays";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual("../../lib/api");
  return {
    ...actual,
    getReplays: vi.fn(),
    getBotStats: vi.fn(),
  };
});

describe("Replays solo gallery page", () => {
  it("renders global deception stats banner and replay cards", async () => {
    vi.mocked(api.getReplays).mockResolvedValue([
      {
        id: "rep-1",
        room_code: "RP0001",
        topic_category: "funny",
        topic_text: "What food combination do you swear by?",
        human_guesses_count: 12,
        correct_guesses_count: 4,
        solo_accuracy_rate: 0.3333,
        solo_bot_fooled_rate: 0.6667,
        created_at: "2026-11-14T10:00:00Z",
      },
    ]);

    vi.mocked(api.getBotStats).mockResolvedValue({
      live_games: {
        total_rounds: 10,
        bot_fooled_count: 6,
        bot_fooled_rate: 0.6,
        total_votes_on_bot: 12,
        total_human_voters: 30,
        human_accuracy_rate: 0.4,
      },
      solo_replays: {
        total_replays_available: 5,
        total_guesses: 40,
        correct_guesses: 15,
        fooled_guesses: 25,
        bot_fooled_rate: 0.625,
      },
      overall: {
        total_encounters: 50,
        total_fooled: 31,
        bot_fooled_rate: 0.62,
      },
    });

    render(
      <BrowserRouter>
        <Replays />
      </BrowserRouter>,
    );

    expect(screen.getByText(/Loading replay cases.../i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Guess The Bot")).toBeInTheDocument();
    });

    // Check stats banner
    expect(screen.getByText("62%")).toBeInTheDocument(); // overall fooled rate
    expect(screen.getByText("10")).toBeInTheDocument(); // live games
    expect(screen.getByText("40")).toBeInTheDocument(); // solo guesses

    // Check replay card
    expect(screen.getByText(/What food combination do you swear by\?/i)).toBeInTheDocument();
    expect(screen.getByText(/67% Fooled/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Guess The Bot/i })).toHaveAttribute(
      "href",
      "/replays/rep-1",
    );
  });
});
