import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { MAX_GAME_TEXT_LENGTH, getSeatColorTheme } from "../../../lib/constants";
import type { ChatMessage, RoundAnswer, RoundSeat } from "../types";

interface ChatPanelProps {
  seats: RoundSeat[];
  mySeatId: string | null;
  answers: RoundAnswer[];
  messages: ChatMessage[];
  typingSeats: Record<string, number>;
  readyToVote: boolean;
  disabled: boolean;
  onSendMessage: (text: string) => boolean;
  onTyping: (isTyping: boolean) => void;
  onReadyToVote: () => void;
}

const TYPING_THROTTLE_MS = 1500;

export function ChatPanel({
  seats,
  mySeatId,
  answers,
  messages,
  typingSeats,
  readyToVote,
  disabled,
  onSendMessage,
  onTyping,
  onReadyToVote,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const lastTypingSentRef = useRef<number>(0);
  const feedEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages.length]);

  const activeTypingAliases = Object.keys(typingSeats)
    .filter((seatId) => seatId !== mySeatId)
    .map((seatId) => seats.find((s) => s.seat_id === seatId)?.alias)
    .filter((alias): alias is string => Boolean(alias));

  let typingLabel = "";
  if (activeTypingAliases.length === 1) {
    typingLabel = `${activeTypingAliases[0]} is typing...`;
  } else if (activeTypingAliases.length === 2) {
    typingLabel = `${activeTypingAliases[0]} and ${activeTypingAliases[1]} are typing...`;
  } else if (activeTypingAliases.length > 2) {
    typingLabel = "Several players are typing...";
  }

  function handleDraftChange(e: ChangeEvent<HTMLInputElement>) {
    const nextValue = e.target.value;
    setDraft(nextValue);
    if (disabled) {
      return;
    }
    const now = Date.now();
    if (nextValue.trim().length > 0) {
      if (now - lastTypingSentRef.current >= TYPING_THROTTLE_MS) {
        onTyping(true);
        lastTypingSentRef.current = now;
      }
    } else if (lastTypingSentRef.current > 0) {
      onTyping(false);
      lastTypingSentRef.current = 0;
    }
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const cleaned = draft.trim();
    if (!cleaned || disabled) {
      return;
    }
    const sent = onSendMessage(cleaned);
    if (sent) {
      setDraft("");
      lastTypingSentRef.current = 0;
    }
  }

  return (
    <div className="space-y-3">
      {answers.length > 0 ? (
        <section
          aria-label="Opening answers"
          className="space-y-2 rounded-2xl border border-slate-800 bg-slate-900/95 p-4 shadow-lg"
        >
          <h2 className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
            Opening Answers
          </h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {answers.map((ans) => {
              const theme = getSeatColorTheme(ans.color_index);
              const isMe = ans.seat_id === mySeatId;
              return (
                <li
                  key={ans.seat_id}
                  className="rounded-xl border border-slate-800 bg-slate-950/70 p-2.5"
                >
                  <div className="flex items-center gap-1.5 text-xs font-semibold">
                    <span aria-hidden="true" className={`h-2 w-2 rounded-full ${theme.dot}`} />
                    <span className={theme.text}>{ans.alias}</span>
                    {isMe ? <span className="text-[10px] text-slate-400">(You)</span> : null}
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-slate-200">{ans.text}</p>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <section
        aria-label="Group chat"
        className="flex flex-col rounded-2xl border border-slate-800 bg-slate-900/95 p-4 shadow-lg"
      >
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
            Live Chat — Spot Who Sounds Off
          </h2>
          <button
            type="button"
            onClick={onReadyToVote}
            disabled={readyToVote || disabled}
            className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-[11px] font-semibold text-slate-200 transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {readyToVote ? "Ready to Vote ✓" : "Ready to Vote"}
          </button>
        </div>

        <div className="h-64 space-y-2.5 overflow-y-auto rounded-xl border border-slate-800 bg-slate-950/70 p-3">
          {messages.length === 0 ? (
            <p className="py-12 text-center text-xs text-slate-500">
              No messages yet. Ask follow-ups to sniff out the bot!
            </p>
          ) : (
            messages.map((msg) => {
              const theme = getSeatColorTheme(msg.color_index);
              const isMe = msg.seat_id === mySeatId;
              return (
                <div key={msg.id} className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}>
                  <div className="mb-0.5 flex items-center gap-1.5 text-[11px]">
                    <span aria-hidden="true" className={`h-2 w-2 rounded-full ${theme.dot}`} />
                    <span className={`font-semibold ${theme.text}`}>{msg.alias}</span>
                    {isMe ? <span className="text-slate-500">(You)</span> : null}
                  </div>
                  <p
                    className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm break-words ${
                      isMe
                        ? "bg-teal-500/20 text-teal-50"
                        : "border border-slate-800 bg-slate-900 text-slate-100"
                    }`}
                  >
                    {msg.text}
                  </p>
                </div>
              );
            })
          )}
          <div ref={feedEndRef} />
        </div>

        <p aria-live="polite" className="min-h-5 pt-1.5 text-xs text-slate-400">
          {typingLabel}
        </p>

        <form onSubmit={handleSubmit} className="mt-1 flex gap-2">
          <input
            type="text"
            maxLength={MAX_GAME_TEXT_LENGTH}
            value={draft}
            onChange={handleDraftChange}
            disabled={disabled}
            aria-label="Chat message"
            placeholder="Say something..."
            className="min-h-11 flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3.5 text-sm text-white placeholder-slate-500 focus:border-teal-400 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!draft.trim() || disabled}
            className="min-h-11 rounded-xl bg-teal-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </section>
    </div>
  );
}
