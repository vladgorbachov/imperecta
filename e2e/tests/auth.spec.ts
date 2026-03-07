import { test, expect } from "@playwright/test";

const TEST_EMAIL = `e2e_${Date.now()}@test.com`;
const TEST_PASSWORD = "E2eTestPass123!";

test.describe("Authentication flow", () => {
  test("should show login page", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("form")).toBeVisible();
    await expect(
      page.locator('input[type="email"], input[name="email"]')
    ).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test("should navigate to register", async ({ page }) => {
    await page.goto("/login");
    const registerLink = page.locator('a[href="/register"]');
    if (await registerLink.isVisible()) {
      await registerLink.click();
      await expect(page).toHaveURL(/register/);
    }
  });

  test("should register new user", async ({ page }) => {
    await page.goto("/register");
    await page.fill(
      'input[name="name"], input[placeholder*="name" i]',
      "E2E Test User"
    );
    await page.fill(
      'input[type="email"], input[name="email"]',
      TEST_EMAIL
    );
    await page.fill('input[type="password"]', TEST_PASSWORD);
    const companyField = page.locator('input[name="company_name"]');
    if (await companyField.isVisible()) {
      await companyField.fill("E2E Corp");
    }
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard|login/, { timeout: 10_000 });
  });

  test("should login and see dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.fill(
      'input[type="email"], input[name="email"]',
      TEST_EMAIL
    );
    await page.fill('input[type="password"]', TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/, { timeout: 10_000 });
    await expect(
      page.locator("main, [role='main'], .dashboard")
    ).toBeVisible();
  });

  test("should reject wrong password", async ({ page }) => {
    await page.goto("/login");
    await page.fill(
      'input[type="email"], input[name="email"]',
      TEST_EMAIL
    );
    await page.fill('input[type="password"]', "WrongPassword123!");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(2000);
    const url = page.url();
    expect(url).toMatch(/login/);
  });
});
