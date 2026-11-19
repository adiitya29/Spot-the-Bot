import type { TopicInfo } from "../types";

interface TopicCardProps {
  topic: TopicInfo;
}

export function TopicCard({ topic }: TopicCardProps) {
  return (
    <section
      aria-label="Round topic"
      className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 shadow-xl backdrop-blur-xl sm:p-5"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-bold tracking-widest text-teal-400 uppercase">
          Topic Prompt
        </span>
        <span className="rounded-full border border-teal-500/20 bg-teal-500/10 px-3 py-0.5 text-xs font-semibold text-teal-300 capitalize">
          {topic.category}
        </span>
      </div>
      <p className="mt-2.5 text-base sm:text-lg leading-snug font-bold text-white">{topic.text}</p>
    </section>
  );
}
