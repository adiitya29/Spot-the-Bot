import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";
import { computeClockOffset, getRemainingSeconds } from "./lib/clockSync";

describe("App shell and routing", () => {
  it("renders landing page with create and join forms", () => {
    window.history.pushState({}, "", "/");
    render(<App />);
    expect(screen.getByRole("heading", { name: "Spot the Bot" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Create a Room" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Join with Code" })).toBeInTheDocument();
  });

  it("computes server clock offset and countdown", () => {
    const offset = computeClockOffset(10_500, 10_000);
    expect(offset).toBe(500);
    expect(getRemainingSeconds(20_500, offset, 15_000)).toBe(5);
    expect(getRemainingSeconds(10_000, offset, 15_000)).toBe(0);
  });
});
