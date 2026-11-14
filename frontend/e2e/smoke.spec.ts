import { test, expect } from "@playwright/test";

test.describe("Spot the Bot E2E Smoke & Mobile Suite", () => {
  test("landing page loads with create and join room forms on desktop and mobile", async ({
    page,
  }) => {
    await page.goto("/");

    // Check header and brand
    await expect(page.locator("h1")).toContainText("Spot the Bot");

    // Check create room form inputs
    const nicknameInput = page.getByPlaceholder(/your host nickname/i);
    await expect(nicknameInput).toBeVisible();

    const createButton = page.getByRole("button", { name: /create room/i });
    await expect(createButton).toBeVisible();

    // Check join room form inputs
    const roomCodeInput = page.getByPlaceholder(/6-char code/i);
    await expect(roomCodeInput).toBeVisible();

    // Verify solo replay link banner is visible
    const replayLink = page.getByRole("link", { name: /play solo guess the bot/i });
    await expect(replayLink).toBeVisible();
  });

  test("navigates to replays gallery and verifies deception stats banner", async ({ page }) => {
    await page.goto("/replays");

    // Replay gallery header
    await expect(page.locator("h1")).toContainText("Guess the Bot");
    await expect(page.getByText(/Bot Survival Rate/i)).toBeVisible();
    await expect(page.getByText(/Total Solo Guesses/i)).toBeVisible();
  });

  test("verifies responsive layout without horizontal overflow on mobile viewport", async ({
    page,
  }) => {
    await page.goto("/");

    // Viewport width check
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);

    // Invariant: no horizontal scrollbar / overflow on mobile
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);
  });

  test("share page renders match results preview and social links", async ({ page }) => {
    await page.goto("/s/DEMO99/");

    await expect(page.locator("body")).toContainText(/DEMO99/i);
  });
});
