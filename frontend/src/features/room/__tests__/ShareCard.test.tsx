import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ShareCard } from "../components/ShareCard";

describe("ShareCard viral component", () => {
  it("renders room code, share card image preview, and social links", () => {
    render(<ShareCard roomCode="WXYZ89" />);

    expect(screen.getByText("Share Match Results")).toBeInTheDocument();
    expect(screen.getByText("Room #WXYZ89")).toBeInTheDocument();

    const img = screen.getByRole("img", { name: /Spot the Bot Results for Room WXYZ89/i });
    expect(img).toHaveAttribute("src", "/api/share/WXYZ89.png");

    const xLink = screen.getByRole("link", { name: /Share on X/i });
    expect(xLink).toHaveAttribute("href", expect.stringContaining("twitter.com/intent/tweet"));

    const waLink = screen.getByRole("link", { name: /WhatsApp/i });
    expect(waLink).toHaveAttribute("href", expect.stringContaining("api.whatsapp.com/send"));

    const saveImg = screen.getByRole("link", { name: /Save Image/i });
    expect(saveImg).toHaveAttribute("href", "/api/share/WXYZ89.png");
  });

  it("copies share page link to clipboard on button click", async () => {
    const user = userEvent.setup();
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: writeTextMock,
      },
      writable: true,
      configurable: true,
    });

    render(<ShareCard roomCode="WXYZ89" />);

    const copyBtn = screen.getByRole("button", { name: /Copy Link/i });
    await user.click(copyBtn);

    expect(writeTextMock).toHaveBeenCalledWith(expect.stringContaining("/s/WXYZ89/"));
    expect(screen.getByText("Copied Link!")).toBeInTheDocument();
  });
});
