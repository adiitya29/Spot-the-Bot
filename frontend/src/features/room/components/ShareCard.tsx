import { useState } from "react";

interface ShareCardProps {
  roomCode: string;
}

export function ShareCard({ roomCode }: ShareCardProps) {
  const [copied, setCopied] = useState(false);

  const cleanCode = roomCode.trim().toUpperCase();
  const shareImageUrl = `/api/share/${cleanCode}.png`;
  const sharePageUrl = `${window.location.origin}/s/${cleanCode}/`;

  const shareText = `We just played Spot the Bot! Can you spot the AI hiding among human players?`;
  const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(
    shareText,
  )}&url=${encodeURIComponent(sharePageUrl)}`;
  const whatsappUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(
    `${shareText} ${sharePageUrl}`,
  )}`;

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(sharePageUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback for older browsers
      const el = document.createElement("textarea");
      el.value = sharePageUrl;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  return (
    <section
      aria-label="Share match results"
      className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-xl backdrop-blur-xl sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-3">
        <div>
          <h3 className="text-base font-bold text-white">Share Match Results</h3>
          <p className="mt-0.5 text-xs text-slate-400">
            Share your match outcome card with friends!
          </p>
        </div>
        <span className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 font-mono text-xs font-bold text-cyan-300">
          Room #{cleanCode}
        </span>
      </div>

      <div className="overflow-hidden rounded-xl border border-white/10 bg-black/60 shadow-inner">
        <img
          src={shareImageUrl}
          alt={`Spot the Bot Results for Room ${cleanCode}`}
          className="h-auto w-full object-cover"
          loading="lazy"
        />
      </div>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <button
          type="button"
          onClick={handleCopyLink}
          className="flex min-h-11 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-3 text-xs font-bold text-white shadow-sm transition-all hover:bg-white/10 active:scale-95"
        >
          {copied ? "Copied Link!" : "Copy Link"}
        </button>

        <a
          href={twitterUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex min-h-11 items-center justify-center rounded-xl bg-sky-500 px-3 text-xs font-bold text-white shadow-sm shadow-sky-500/20 transition-all hover:bg-sky-400 active:scale-95"
        >
          Share on X
        </a>

        <a
          href={whatsappUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex min-h-11 items-center justify-center rounded-xl bg-emerald-600 px-3 text-xs font-bold text-white shadow-sm shadow-emerald-600/20 transition-all hover:bg-emerald-500 active:scale-95"
        >
          WhatsApp
        </a>

        <a
          href={shareImageUrl}
          download={`spot-the-bot-${cleanCode}.png`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex min-h-11 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-3 text-xs font-bold text-slate-200 shadow-sm transition-all hover:bg-white/10 active:scale-95"
        >
          Save Image
        </a>
      </div>
    </section>
  );
}
