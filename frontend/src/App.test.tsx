import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { computeClockOffset, getRemainingSeconds } from "./lib/clockSync";
import { initialRoomState, roomReducer } from "./features/room/reducer";
import { useRoomStore } from "./features/room/roomStore";

class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    queueMicrotask(() => {
      this.onopen?.();
    });
  }

  send = vi.fn();
  close = vi.fn();
}

describe("Phase 0 frontend scaffold", () => {
  beforeEach(() => {
    useRoomStore.getState().reset();
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok" }),
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders landing scaffold and connects echo websocket", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Spot the Bot" })).toBeInTheDocument();
    expect(await screen.findByText("ok")).toBeInTheDocument();
    expect(await screen.findByText("connected")).toBeInTheDocument();
  });

  it("applies reducer transitions cleanly", () => {
    const connected = roomReducer(initialRoomState, { type: "ws_connected" });
    expect(connected.status).toBe("connected");
    const echoed = roomReducer(connected, { type: "ws_echo", payload: "hi" });
    expect(echoed.lastEcho).toBe("hi");
  });

  it("computes server clock offset and countdown", () => {
    const offset = computeClockOffset(10_500, 10_000);
    expect(offset).toBe(500);
    expect(getRemainingSeconds(20_500, offset, 15_000)).toBe(5);
    expect(getRemainingSeconds(10_000, offset, 15_000)).toBe(0);
  });
});
