import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ConnectionBanner } from "../components/ConnectionBanner";

describe("ConnectionBanner component", () => {
  it("renders nothing when connected and no error", () => {
    const { container } = render(
      <MemoryRouter>
        <ConnectionBanner status="connected" code="AB2C3D" />
      </MemoryRouter>,
    );
    expect(container.firstChild?.childNodes.length).toBe(0);
  });

  it("renders connecting status banner with role status", () => {
    render(
      <MemoryRouter>
        <ConnectionBanner status="connecting" code="AB2C3D" />
      </MemoryRouter>,
    );
    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent("Connecting to room...");
  });

  it("renders reconnecting banner with role status", () => {
    render(
      <MemoryRouter>
        <ConnectionBanner status="reconnecting" code="AB2C3D" />
      </MemoryRouter>,
    );
    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent("Connection lost. Reconnecting to room...");
  });

  it("renders evicted banner with role alert when duplicate tab connects", () => {
    render(
      <MemoryRouter>
        <ConnectionBanner status="evicted" code="AB2C3D" />
      </MemoryRouter>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("You opened this room in another tab. This tab is now paused.");
  });

  it("renders auth_error alert with rejoin link", () => {
    render(
      <MemoryRouter>
        <ConnectionBanner status="auth_error" code="AB2C3D" />
      </MemoryRouter>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Your guest session expired or is invalid for this room.");
    const link = screen.getByRole("link", { name: "Rejoin" });
    expect(link).toHaveAttribute("href", "/join/AB2C3D");
  });

  it("renders error alert with dismiss button and fires callback", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    render(
      <MemoryRouter>
        <ConnectionBanner
          status="connected"
          code="AB2C3D"
          error={{ code: "invalid_phase", message: "Cannot perform action in this phase." }}
          onDismissError={onDismiss}
        />
      </MemoryRouter>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Cannot perform action in this phase.");
    const btn = screen.getByRole("button", { name: "Dismiss" });
    await user.click(btn);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});

