import { describe, expect, it } from "vitest";
import { computeClockOffset, formatCountdown, getRemainingSeconds } from "../../../lib/clockSync";

describe("clockSync helpers", () => {
  it("adjusts countdown using server clock offset", () => {
    const offset = computeClockOffset(100_000, 95_000);
    expect(offset).toBe(5_000);

    // Ends at 130s server time while local clock reads 100s (+5s offset = 105s server time -> 25s left)
    expect(getRemainingSeconds(130_000, offset, 100_000)).toBe(25);
    expect(getRemainingSeconds(104_000, offset, 100_000)).toBe(0);
  });

  it("formats MM:SS countdown cleanly", () => {
    expect(formatCountdown(125)).toBe("2:05");
    expect(formatCountdown(45)).toBe("0:45");
    expect(formatCountdown(0)).toBe("0:00");
  });
});
