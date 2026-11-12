import type { TopicInfo } from "../types";

interface TopicCardProps {
  topic: TopicInfo;
}

export function TopicCard({ topic }: TopicCardProps) {
  return (
    <section
      aria-label="Round topic"
      className="rounded-2xl border border-slate-800 bg-slate-900/95 p-4 shadow-lg"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          Topic Prompt
        </span>
        <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-[11px] font-medium text-teal-300 capitalize">
          {topic.category}
        </span>
      </div>
      <p className="mt-2 text-base leading-snug font-semibold text-white">{topic.text}</p>
    </section>
  );
}

