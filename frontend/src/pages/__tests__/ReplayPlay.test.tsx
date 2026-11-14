import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import { ReplayPlay } from "../ReplayPlay";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual("../../lib/api");
  return {
    ...actual,
    getReplay: vi.fn(),
    submitSoloGuess: vi.fn(),
  };
});

describe("ReplayPlay interactive solo game page", () => {
  it("renders replay transcript, selects alias, and reveals guess outcome", async () => {
    const user = userEvent.setup();

    vi.mocked(api.getReplay).mockResolvedValue({
      id: "rep-1",
      room_code: "RP0001",
      topic_category: "funny",
      topic_text: "What food combination do you swear by?",
      human_guesses_count: 5,
      correct_guesses_count: 2,
      solo_accuracy_rate: 0.4,
      solo_bot_fooled_rate: 0.6,
      created_at: "2026-11-14T10:00:00Z",
      transcript: {
        participants: [
          { seat_id: "s1", alias: "Teal Otter", color_index: 0 },
          { seat_id: "s2", alias: "Coral Fox", color_index: 1 },
        ],
        answers: [
          { seat_id: "s1", alias: "Teal Otter", text: "fries in shake" },
          { seat_id: "s2", alias: "Coral Fox", text: "peanut butter burger" },
        ],
        messages: [
          {
            id: "m1",
            seat_id: "s1",
            alias: "Teal Otter",
            text: "wait that's weird",
            latency_ms: 2000,
          },
          {
            id: "m2",
            seat_id: "s2",
            alias: "Coral Fox",
            text: "nah fr it's so good",
            latency_ms: 1800,
          },
        ],
      },
    });

    vi.mocked(api.submitSoloGuess).mockResolvedValue({
      correct: true,
      guessed_alias: "Teal Otter",
      bot_alias: "Teal Otter",
      human_guesses_count: 6,
      correct_guesses_count: 3,
      solo_accuracy_rate: 0.5,
      solo_bot_fooled_rate: 0.5,
      explanation: "You correctly spotted Teal Otter as the AI bot!",
    });

    render(
      <MemoryRouter initialEntries={["/replays/rep-1"]}>
        <Routes>
          <Route path="/replays/:id" element={<ReplayPlay />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/Loading replay case.../i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/What food combination do you swear by\?/i)).toBeInTheDocument();
    });

    // Verify transcript elements
    expect(screen.getByText("fries in shake")).toBeInTheDocument();
    expect(screen.getByText("wait that's weird")).toBeInTheDocument();

    // Select guess alias
    const guessButton = screen.getByRole("button", { name: /Teal Otter/i });
    await user.click(guessButton);

    const submitBtn = screen.getByRole("button", { name: /Submit Guess/i });
    await user.click(submitBtn);

    expect(api.submitSoloGuess).toHaveBeenCalledWith("rep-1", "Teal Otter");

    // Outcome card displayed
    await waitFor(() => {
      expect(screen.getByText(/Correct! Bot Spotted/i)).toBeInTheDocument();
    });
    expect(
      screen.getByText(/You correctly spotted Teal Otter as the AI bot!/i),
    ).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument(); // 0.5 solo accuracy
  });
});
