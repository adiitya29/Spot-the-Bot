import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Leaderboard } from "../components/Leaderboard";
import { RevealStage } from "../components/RevealStage";
import { VotePanel } from "../components/VotePanel";

describe("Phase 4 voting, reveal, and leaderboard components", () => {
  it("excludes self seat from VotePanel and locks in selected target vote", async () => {
    const user = userEvent.setup();
    const onCastVote = vi.fn();

    render(
      <VotePanel
        seats={[
          { seat_id: "s1", alias: "Teal Otter", color_index: 0 },
          { seat_id: "s2", alias: "Coral Fox", color_index: 1 },
          { seat_id: "s3", alias: "Amber Lynx", color_index: 2 },
        ]}
        mySeatId="s1"
        answers={[
          { seat_id: "s1", alias: "Teal Otter", color_index: 0, text: "My answer" },
          { seat_id: "s2", alias: "Coral Fox", color_index: 1, text: "Suspect reply" },
          { seat_id: "s3", alias: "Amber Lynx", color_index: 2, text: "Normal human text" },
        ]}
        votesCast={1}
        totalHumans={3}
        myVoteTargetSeatId={null}
        disabled={false}
        onCastVote={onCastVote}
      />,
    );

    expect(screen.queryByRole("button", { name: /Teal Otter/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Coral Fox/i }));
    await user.click(screen.getByRole("button", { name: /Lock In Vote/i }));
    expect(onCastVote).toHaveBeenCalledWith("s2");
  });

  it("renders RevealStage with bot identity, tallies, and +100 badges", () => {
    render(
      <RevealStage
        reveal={{
          round_id: "r1",
          round_number: 1,
          total_rounds: 3,
          bot_seat_id: "s2",
          bot_alias: "Coral Fox",
          votes_for_bot: 2,
          human_voters: 3,
          bot_fooled: false,
          tally: [
            {
              seat_id: "s2",
              alias: "Coral Fox",
              color_index: 1,
              is_bot: true,
              player_id: null,
              nickname: "Bot",
              votes_received: 2,
              voter_seat_ids: ["s1", "s3"],
              voted_target_seat_id: null,
              round_points: 0,
              total_score: null,
            },
            {
              seat_id: "s1",
              alias: "Teal Otter",
              color_index: 0,
              is_bot: false,
              player_id: "p1",
              nickname: "Alice",
              votes_received: 1,
              voter_seat_ids: ["s4"],
              voted_target_seat_id: "s2",
              round_points: 100,
              total_score: 100,
            },
          ],
          leaderboard: [
            {
              rank: 1,
              player_id: "p1",
              nickname: "Alice",
              is_host: true,
              connected: true,
              score: 100,
              round_points: 100,
            },
          ],
        }}
        mySeatId="s1"
        myPlayerId="p1"
      />,
    );

    expect(screen.getByText(/Coral Fox was the AI Bot!/i)).toBeInTheDocument();
    expect(screen.getByText(/Bot Spotted!/i)).toBeInTheDocument();
    expect(screen.getAllByText("+100")).toHaveLength(2);
  });

  it("renders Game Over Leaderboard and fires onPlayAgain for host only", async () => {
    const user = userEvent.setup();
    const onPlayAgain = vi.fn();

    render(
      <Leaderboard
        entries={[
          {
            rank: 1,
            player_id: "p1",
            nickname: "Alice",
            is_host: true,
            connected: true,
            score: 300,
          },
          {
            rank: 2,
            player_id: "p2",
            nickname: "Bob",
            is_host: false,
            connected: true,
            score: 200,
          },
        ]}
        myPlayerId="p1"
        roundsSummary={[
          {
            round_number: 1,
            topic_text: "Worst movie snack?",
            topic_category: "funny",
            bot_alias: "Coral Fox",
            votes_for_bot: 2,
            human_voters: 3,
            bot_fooled: false,
          },
        ]}
        botFooledCount={1}
        totalRounds={3}
        isGameOver
        isHost
        onPlayAgain={onPlayAgain}
      />,
    );

    expect(screen.getByText(/Game Over — Final Standings/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Play Again/i }));
    expect(onPlayAgain).toHaveBeenCalledTimes(1);
  });
});
