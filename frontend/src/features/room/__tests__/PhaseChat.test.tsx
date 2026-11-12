import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnswerBox } from "../components/AnswerBox";
import { ChatPanel } from "../components/ChatPanel";
import { PhaseHeader } from "../components/PhaseHeader";
import { TopicCard } from "../components/TopicCard";

describe("Phase 3 gameplay components", () => {
  it("renders PhaseHeader and TopicCard with alias and clock-synced timer", () => {
    render(
      <div>
        <PhaseHeader
          code="AB2C3D"
          phase="answer"
          roundNumber={1}
          totalRounds={3}
          phaseEndsAtMs={Date.now() + 45_000}
          clockOffsetMs={0}
          mySeat={{ seat_id: "s1", alias: "Teal Otter", color_index: 0 }}
        />
        <TopicCard topic={{ id: 1, category: "opinion", text: "Is cereal cold soup?" }} />
      </div>,
    );

    expect(screen.getByText("Round 1 of 3")).toBeInTheDocument();
    expect(screen.getByText("You are Teal Otter")).toBeInTheDocument();
    expect(screen.getByText("Is cereal cold soup?")).toBeInTheDocument();
  });

  it("submits AnswerBox text and shows locked confirmation state", async () => {
    const user = userEvent.setup();
    const onSubmitAnswer = vi.fn();

    const { rerender } = render(
      <AnswerBox
        hasAnswered={false}
        submittedAnswer={null}
        disabled={false}
        onSubmitAnswer={onSubmitAnswer}
      />,
    );

    await user.type(screen.getByLabelText("Write your opening answer"), "Definitely not soup");
    await user.click(screen.getByRole("button", { name: "Lock In Answer" }));
    expect(onSubmitAnswer).toHaveBeenCalledWith("Definitely not soup");

    rerender(
      <AnswerBox
        hasAnswered={true}
        submittedAnswer="Definitely not soup"
        disabled={false}
        onSubmitAnswer={onSubmitAnswer}
      />,
    );
    expect(screen.getByText("Answer locked in!")).toBeInTheDocument();
    expect(screen.getByText("Definitely not soup")).toBeInTheDocument();
  });

  it("renders ChatPanel answers, messages, typing indicators, and sends messages", async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn().mockReturnValue(true);
    const onTyping = vi.fn();
    const onReadyToVote = vi.fn();

    render(
      <ChatPanel
        seats={[
          { seat_id: "s1", alias: "Teal Otter", color_index: 0 },
          { seat_id: "s2", alias: "Coral Fox", color_index: 1 },
        ]}
        mySeatId="s1"
        answers={[{ seat_id: "s2", alias: "Coral Fox", color_index: 1, text: "Yes, cold soup." }]}
        messages={[
          {
            id: 1,
            round_id: "r1",
            seat_id: "s2",
            alias: "Coral Fox",
            color_index: 1,
            text: "Wait why are you booing me",
            client_msg_id: null,
            created_at: 1000,
          },
        ]}
        typingSeats={{ s2: Date.now() + 3000 }}
        readyToVote={false}
        disabled={false}
        onSendMessage={onSendMessage}
        onTyping={onTyping}
        onReadyToVote={onReadyToVote}
      />,
    );

    expect(screen.getByText("Yes, cold soup.")).toBeInTheDocument();
    expect(screen.getByText("Wait why are you booing me")).toBeInTheDocument();
    expect(screen.getByText("Coral Fox is typing...")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Chat message"), "Because milk is not broth");
    expect(onTyping).toHaveBeenCalledWith(true);
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSendMessage).toHaveBeenCalledWith("Because milk is not broth");

    await user.click(screen.getByRole("button", { name: "Ready to Vote" }));
    expect(onReadyToVote).toHaveBeenCalledTimes(1);
  });
});

