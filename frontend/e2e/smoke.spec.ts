import { test, expect } from "@playwright/test";

test.describe("Spot the Bot E2E Smoke & Mobile Suite", () => {
  test("landing page loads with create and join room forms on desktop and mobile", async ({
    page,
  }) => {
    await page.goto("/");

    // Check header and brand
    await expect(page.locator("h1")).toContainText("Spot the Bot");

    // Check create room form inputs
    const nicknameInput = page.locator("#create-nickname");
    await expect(nicknameInput).toBeVisible();

    const createButton = page.getByRole("button", { name: /create room/i });
    await expect(createButton).toBeVisible();

    // Check join room form inputs
    const roomCodeInput = page.getByLabel("Room code");
    await expect(roomCodeInput).toBeVisible();
  });

  test("navigates to replays gallery and verifies deception stats banner", async ({ page }) => {
    // Intercept replay API calls with valid BotGlobalStats structure
    await page.route("**/api/stats/bot/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          live_games: {
            total_rounds: 10,
            bot_fooled_count: 6,
            bot_fooled_rate: 0.6,
            total_votes_on_bot: 12,
            total_human_voters: 30,
            human_accuracy_rate: 0.4,
          },
          solo_replays: {
            total_replays_available: 5,
            total_guesses: 25,
            correct_guesses: 10,
            fooled_guesses: 15,
            bot_fooled_rate: 0.6,
          },
          overall: {
            total_encounters: 35,
            total_fooled: 21,
            bot_fooled_rate: 0.6,
          },
        }),
      });
    });

    await page.route("**/api/replays/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "test-replay-uuid-1",
            room_code: "XYZ999",
            topic_category: "technology",
            topic_text: "Is artificial intelligence conscious?",
            human_guesses_count: 5,
            correct_guesses_count: 2,
            bot_fooled_original: true,
            created_at: new Date().toISOString(),
          },
        ]),
      });
    });

    await page.goto("/replays");

    // Replay gallery header and stats banner
    await expect(page.locator("h1")).toContainText(/Guess The Bot/i);
    await expect(page.getByText(/AI Deception Rate/i)).toBeVisible();
    await expect(page.getByText(/Live Games Played/i)).toBeVisible();
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
    await page.goto("/share/DEMO99");

    await expect(page.locator("body")).toContainText(/DEMO99/i);
    await expect(page.getByRole("link", { name: /share on x/i })).toBeVisible();
  });
});
