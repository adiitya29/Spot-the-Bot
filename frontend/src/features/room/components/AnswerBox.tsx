import { useState, type FormEvent } from "react";
import { MAX_GAME_TEXT_LENGTH } from "../../../lib/constants";

interface AnswerBoxProps {
  hasAnswered: boolean;
  submittedAnswer: string | null;
  disabled: boolean;
  onSubmitAnswer: (text: string) => void;
}

export function AnswerBox({
  hasAnswered,
  submittedAnswer,
  disabled,
  onSubmitAnswer,
}: AnswerBoxProps) {
  const [text, setText] = useState("");
  const remaining = MAX_GAME_TEXT_LENGTH - text.length;
  const trimmed = text.trim();

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!trimmed || hasAnswered || disabled) {
      return;
    }
    onSubmitAnswer(trimmed);
  }

  if (hasAnswered) {
    return (
      <section
        aria-label="Answer submitted"
        className="space-y-3 rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-5 shadow-xl backdrop-blur-xl sm:p-6"
      >
        <div className="flex items-center gap-2.5 text-sm font-bold text-emerald-300">
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400 animate-pulse"
          />
          <span>Answer locked in!</span>
        </div>
        {submittedAnswer ? (
          <p className="rounded-xl border border-emerald-500/20 bg-slate-950/80 p-3.5 text-sm font-medium leading-relaxed text-slate-100">
            {submittedAnswer}
          </p>
        ) : null}
        <p className="text-xs text-slate-400">
          Waiting for everyone else to submit before chat begins...
        </p>
      </section>
    );
  }

  return (
    <section
      aria-label="Submit answer"
      className="rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-xl backdrop-blur-xl sm:p-6"
    >
      <form onSubmit={handleSubmit} className="space-y-3.5">
        <div className="flex items-center justify-between">
          <label htmlFor="answer-input" className="text-sm font-bold text-white">
            Write your opening answer
          </label>
          <span
            className={`font-mono text-xs font-medium ${remaining <= 30 ? "text-amber-400" : "text-slate-400"}`}
          >
            {remaining} left
          </span>
        </div>

        <textarea
          id="answer-input"
          rows={3}
          maxLength={MAX_GAME_TEXT_LENGTH}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabled}
          placeholder="Answer naturally like yourself — everyone reads these together..."
          className="w-full resize-none rounded-xl border border-white/10 bg-black/50 px-4 py-3 text-sm text-white placeholder-slate-500 shadow-inner transition-all focus:border-teal-400 focus:bg-slate-950 focus:ring-1 focus:ring-teal-400/40 focus:outline-none disabled:opacity-50"
        />

        <button
          type="submit"
          disabled={!trimmed || disabled}
          className="min-h-11 w-full rounded-xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 px-5 text-sm font-bold text-slate-950 shadow-lg shadow-teal-500/20 transition-all hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100 disabled:active:scale-100"
        >
          Lock In Answer
        </button>
      </form>
    </section>
  );
}
