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
    <div className={answers.length > 0 ? "grid gap-4 md:grid-cols-12 md:items-start" : "space-y-4"}>
      {answers.length > 0 ? (
        <section
          aria-label="Opening answers"
          className="flex flex-col rounded-2xl border border-white/10 bg-slate-900/60 p-4 shadow-xl backdrop-blur-xl md:col-span-5 sm:p-5"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-xs font-bold tracking-widest text-teal-400 uppercase">
              Opening Answers
            </h2>
            <span className="text-[11px] font-mono text-slate-400">
              {answers.length} {answers.length === 1 ? "answer" : "answers"}
            </span>
          </div>
          <ul className="max-h-48 space-y-2.5 overflow-y-auto pr-1 md:max-h-[380px]">
            {answers.map((ans) => {
              const theme = getSeatColorTheme(ans.color_index);
              const isMe = ans.seat_id === mySeatId;
              return (
                <li
                  key={ans.seat_id}
                  className="rounded-xl border border-white/5 bg-black/40 p-3 shadow-inner transition-colors hover:border-white/15"
                >
                  <div className="flex items-center gap-2 text-xs font-bold">
                    <span
                      aria-hidden="true"
                      className={`h-2.5 w-2.5 rounded-full ring-2 ring-white/10 ${theme.dot}`}
                    />
                    <span className={theme.text}>{ans.alias}</span>
                    {isMe ? (
                      <span className="rounded bg-white/10 px-1.5 py-0.2 text-[10px] font-medium text-slate-300">
                        (You)
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-200">{ans.text}</p>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <section
        aria-label="Group chat"
        className={`flex flex-col rounded-2xl border border-white/10 bg-slate-900/60 p-4 shadow-xl backdrop-blur-xl sm:p-5 ${
          answers.length > 0 ? "md:col-span-7" : ""
        }`}
      >
        <div className="mb-3 flex items-center justify-between gap-2 border-b border-white/5 pb-3">
          <div>
            <h2 className="text-xs font-bold tracking-widest text-teal-400 uppercase">
              Live Chat — Spot Who Sounds Off
            </h2>
            <p className="text-[11px] text-slate-400">Ask probing questions to unmask the AI</p>
          </div>
          <button
            type="button"
            onClick={onReadyToVote}
            disabled={readyToVote || disabled}
            className={`rounded-xl border px-3 py-1.5 text-xs font-bold transition-all disabled:cursor-not-allowed ${
              readyToVote
                ? "border-emerald-500/40 bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30"
                : "border-white/10 bg-white/5 text-slate-200 hover:border-white/20 hover:bg-white/10 disabled:opacity-40"
            }`}
          >
            {readyToVote ? "Ready to Vote ✓" : "Ready to Vote"}
          </button>
        </div>

        <div className="h-64 space-y-3 overflow-y-auto rounded-xl border border-white/5 bg-black/45 p-3.5 shadow-inner sm:h-72 md:h-80">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <span className="text-2xl mb-1 opacity-60">💬</span>
              <p className="text-xs text-slate-400">
                No messages yet. Ask follow-ups to sniff out the bot!
              </p>
            </div>
          ) : (
            messages.map((msg) => {
              const theme = getSeatColorTheme(msg.color_index);
              const isMe = msg.seat_id === mySeatId;
              return (
                <div key={msg.id} className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}>
                  <div className="mb-1 flex items-center gap-1.5 text-[11px]">
                    <span
                      aria-hidden="true"
                      className={`h-2 w-2 rounded-full ring-1 ring-white/10 ${theme.dot}`}
                    />
                    <span className={`font-bold ${theme.text}`}>{msg.alias}</span>
                    {isMe ? <span className="text-slate-500 text-[10px]">(You)</span> : null}
                  </div>
                  <p
                    className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed break-words shadow-sm ${
                      isMe
                        ? "border border-teal-500/30 bg-teal-500/20 text-teal-50"
                        : "border border-white/10 bg-slate-900/90 text-slate-100"
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

        <p aria-live="polite" className="min-h-5 pt-1.5 font-mono text-[11px] text-amber-300/80">
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
            className="min-h-11 flex-1 rounded-xl border border-white/10 bg-black/50 px-4 text-sm text-white placeholder-slate-500 shadow-inner transition-all focus:border-teal-400 focus:bg-slate-950 focus:ring-1 focus:ring-teal-400/40 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!draft.trim() || disabled}
            className="min-h-11 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-400 px-5 text-sm font-bold text-slate-950 shadow-md shadow-teal-500/20 transition-all hover:brightness-110 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100 disabled:active:scale-100"
          >
            Send
          </button>
        </form>
      </section>
    </div>
  );
}
