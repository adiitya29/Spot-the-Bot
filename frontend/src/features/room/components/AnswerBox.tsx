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
        className="space-y-3 rounded-2xl border border-emerald-500/30 bg-slate-900/95 p-5 shadow-lg"
      >
        <div className="flex items-center gap-2 text-sm font-semibold text-emerald-300">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
          <span>Answer locked in!</span>
        </div>
        {submittedAnswer ? (
          <p className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 text-sm text-slate-200">
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
      className="rounded-2xl border border-slate-800 bg-slate-900/95 p-5 shadow-lg"
    >
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex items-center justify-between">
          <label htmlFor="answer-input" className="text-sm font-semibold text-white">
            Write your opening answer
          </label>
          <span
            className={`font-mono text-xs ${remaining <= 30 ? "text-amber-300" : "text-slate-400"}`}
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
          className="w-full resize-none rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-teal-400 focus:outline-none disabled:opacity-50"
        />

        <button
          type="submit"
          disabled={!trimmed || disabled}
          className="min-h-11 w-full rounded-xl bg-teal-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Lock In Answer
        </button>
      </form>
    </section>
  );
}

