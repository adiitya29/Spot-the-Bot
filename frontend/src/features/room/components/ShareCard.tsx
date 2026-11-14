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
      className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-lg"
    >
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-white">Share Match Results</h3>
          <p className="text-xs text-slate-400">Share your match outcome card with friends!</p>
        </div>
        <span className="rounded-full bg-cyan-500/15 px-2.5 py-0.5 text-xs font-semibold text-cyan-300">
          Room #{cleanCode}
        </span>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <img
          src={shareImageUrl}
          alt={`Spot the Bot Results for Room ${cleanCode}`}
          className="h-auto w-full object-cover"
          loading="lazy"
        />
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <button
          type="button"
          onClick={handleCopyLink}
          className="flex min-h-10 items-center justify-center rounded-xl bg-slate-800 px-3 text-xs font-semibold text-white transition hover:bg-slate-700"
        >
          {copied ? "Copied Link!" : "Copy Link"}
        </button>

        <a
          href={twitterUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex min-h-10 items-center justify-center rounded-xl bg-sky-600/80 px-3 text-xs font-semibold text-white transition hover:bg-sky-500"
        >
          Share on X
        </a>

        <a
          href={whatsappUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex min-h-10 items-center justify-center rounded-xl bg-emerald-600/80 px-3 text-xs font-semibold text-white transition hover:bg-emerald-500"
        >
          WhatsApp
        </a>

        <a
          href={shareImageUrl}
          download={`spot-the-bot-${cleanCode}.png`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex min-h-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-800/80 px-3 text-xs font-semibold text-slate-200 transition hover:bg-slate-700"
        >
          Save Image
        </a>
      </div>
    </section>
  );
}

