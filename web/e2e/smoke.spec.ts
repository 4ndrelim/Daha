import { expect, test, type Page } from "@playwright/test";

/** Collect browser crashes so every step can assert "no page errors". */
function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

async function demoLogin(page: Page, name: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await page.waitForURL(/\/(home|onboarding)/);
}

test("demo login → home → search → item → post a request → every tab", async ({ page }) => {
  const errors = watchErrors(page);
  const pageViews: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/api/events")) {
      for (const e of r.postDataJSON()?.events ?? []) if (e.type === "page_view") pageViews.push(e.payload?.path);
    }
  });

  // 1. One-tap demo login lands on Home.
  await demoLogin(page, "Maya");
  await expect(page).toHaveURL(/\/home/);
  await expect(page.locator("main:visible")).toContainText(/\S/);

  // 2. Search finds the seeded graphing calculator.
  await page.goto("/explore?q=" + encodeURIComponent("graphing calculator"));
  const first = page.locator("main:visible a[href^='/items/']").first();
  await expect(first).toContainText(/calculator/i);

  // 3. The item page opens.
  await first.click();
  await page.waitForURL(/\/items\/\d+/);
  await expect(page.locator("main:visible h1")).toContainText(/calculator/i);

  // 4. Post a request; it opens its own page.
  await page.goto("/add/request?text=" + encodeURIComponent("anyone have a tape measure tonight? (e2e)"));
  await page.locator("main:visible").getByRole("button", { name: /^Post/ }).click();
  await page.waitForURL(/\/requests\/\d+/);
  await expect(page.locator("main:visible")).toContainText(/tape measure/i);

  // 5. Every bottom-nav tab and the inbox render without the error screen.
  for (const path of ["/home", "/explore", "/communities", "/messages", "/notifications", "/profile"]) {
    await page.goto(path);
    await expect(page.locator("main:visible")).toContainText(/\S/);
    await expect(page.getByText("Something went wrong")).toHaveCount(0);
  }

  // 6. Leaderboard: podium with the three awards, both tabs, nickname only.
  await page.goto("/leaderboard");
  const board = page.locator("main:visible");
  await expect(board.getByRole("list", { name: "Podium" })).toContainText("The Karma GOAT");
  await board.getByRole("tab", { name: "All time" }).click();
  await expect(board.getByRole("list", { name: "Dorm ranking" })).toBeVisible();
  await expect(board).not.toContainText("Maya Chen");

  // 7. page_view events are sent with the path only (never the query string).
  await expect.poll(() => pageViews.length).toBeGreaterThan(3);
  expect(pageViews.every((p) => typeof p === "string" && !p.includes("?"))).toBe(true);
  expect(pageViews).toContain("/profile");

  expect(errors).toEqual([]);
});

test("logged-out visitors are sent to login", async ({ page }) => {
  await page.goto("/home");
  await page.waitForURL(/\/login\?next=/);
});
