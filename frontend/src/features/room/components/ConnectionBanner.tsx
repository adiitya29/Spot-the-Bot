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
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2.5 text-xs text-amber-200"
        >
          Connecting to room...
        </div>
      ) : null}

      {status === "reconnecting" ? (
        <div
          role="status"
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2.5 text-xs text-amber-200"
        >
          Connection lost. Reconnecting to room...
        </div>
      ) : null}

      {status === "evicted" ? (
        <div
          role="alert"
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2.5 text-xs text-amber-200"
        >
          You opened this room in another tab. This tab is now paused.
        </div>
      ) : null}

      {status === "auth_error" ? (
        <div
          role="alert"
          className="flex items-center justify-between rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-200"
        >
          <span>Your guest session expired or is invalid for this room.</span>
          <Link to={`/join/${code}`} className="font-semibold text-white underline">
            Rejoin
          </Link>
        </div>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-200"
        >
          <span>{error.message}</span>
          {onDismissError ? (
            <button
              type="button"
              onClick={onDismissError}
              className="font-semibold text-rose-100 underline"
            >
              Dismiss
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
