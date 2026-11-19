import { Link } from "react-router-dom";
import type { ErrorPayload, WsSocketStatus } from "../types";

export interface ConnectionBannerProps {
  status: WsSocketStatus;
  code: string;
  error?: ErrorPayload | null;
  onDismissError?: () => void;
}

export function ConnectionBanner({ status, code, error, onDismissError }: ConnectionBannerProps) {
  return (
    <div className="space-y-2">
      {status === "connecting" ? (
        <div
          role="status"
          className="flex items-center gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/15 px-4 py-3 text-xs font-semibold text-amber-200 shadow-sm backdrop-blur-md"
        >
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-amber-400 animate-ping" />
          <span>Connecting to room...</span>
        </div>
      ) : null}

      {status === "reconnecting" ? (
        <div
          role="status"
          className="flex items-center gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/15 px-4 py-3 text-xs font-semibold text-amber-200 shadow-sm backdrop-blur-md"
        >
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-amber-400 animate-ping" />
          <span>Connection lost. Reconnecting to room...</span>
        </div>
      ) : null}

      {status === "evicted" ? (
        <div
          role="alert"
          className="flex items-center gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/15 px-4 py-3 text-xs font-semibold text-amber-200 shadow-sm backdrop-blur-md"
        >
          <span aria-hidden="true">⏸</span>
          <span>You opened this room in another tab. This tab is now paused.</span>
        </div>
      ) : null}

      {status === "auth_error" ? (
        <div
          role="alert"
          className="flex items-center justify-between rounded-xl border border-rose-500/30 bg-rose-500/15 px-4 py-3 text-xs font-semibold text-rose-200 shadow-sm backdrop-blur-md"
        >
          <span>Your guest session expired or is invalid for this room.</span>
          <Link to={`/join/${code}`} className="font-bold text-white underline hover:text-rose-100">
            Rejoin
          </Link>
        </div>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 rounded-xl border border-rose-500/30 bg-rose-500/15 px-4 py-3 text-xs font-semibold text-rose-200 shadow-sm backdrop-blur-md"
        >
          <span>{error.message}</span>
          {onDismissError ? (
            <button
              type="button"
              onClick={onDismissError}
              className="font-bold text-rose-100 underline hover:text-white"
            >
              Dismiss
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
