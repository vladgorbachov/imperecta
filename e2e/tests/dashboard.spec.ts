import { test, expect } from "@playwright/test";

async function login(
  page: import("@playwright/test").Page,
  email = "e2e@test.com",
  password = "E2eTestPass123!"
) {
  await page.goto("/login");
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/dashboard/, { timeout: 10_000 });
}

test.describe("Dashboard", () => {
  test("should load without errors", async ({ page }) => {
    const testEmail = `e2e_dash_${Date.now()}@test.com`;
    await page.goto("/register");
    await page.fill('input[name="name"], input[placeholder*="name" i]', "E2E Dashboard");
    await page.fill('input[type="email"], input[name="email"]', testEmail);
    await page.fill('input[type="password"]', "E2eTestPass123!");
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/, { timeout: 10_000 });

    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.waitForTimeout(3000);
    expect(errors.length).toBe(0);
  });

  test("should show KPI cards", async ({ page }) => {
    const testEmail = `e2e_kpi_${Date.now()}@test.com`;
    await page.goto("/register");
    await page.fill('input[name="name"]', "E2E KPI");
    await page.fill('input[type="email"]', testEmail);
    await page.fill('input[type="password"]', "E2eTestPass123!");
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/, { timeout: 10_000 });

    await page.waitForTimeout(3000);
    const cards = page.locator("[class*='card'], [class*='Card']");
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });

  test("sidebar navigation works", async ({ page }) => {
    const testEmail = `e2e_nav_${Date.now()}@test.com`;
    await page.goto("/register");
    await page.fill('input[name="name"]', "E2E Nav");
    await page.fill('input[type="email"]', testEmail);
    await page.fill('input[type="password"]', "E2eTestPass123!");
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/, { timeout: 10_000 });

    const productsLink = page.locator('a[href="/products"]');
    if (await productsLink.isVisible()) {
      await productsLink.click();
      await expect(page).toHaveURL(/products/);
    }
  });
});
