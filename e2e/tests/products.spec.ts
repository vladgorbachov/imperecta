import { test, expect } from "@playwright/test";

test.describe("Products", () => {
  test("should show products page", async ({ page }) => {
    const testEmail = `e2e_prod_${Date.now()}@test.com`;
    await page.goto("/register");
    await page.fill('input[name="name"]', "E2E Products");
    await page.fill('input[type="email"]', testEmail);
    await page.fill('input[type="password"]', "E2eTestPass123!");
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/, { timeout: 10_000 });

    await page.goto("/products");
    await page.waitForTimeout(2000);
    const content = page.locator("main, [role='main']");
    await expect(content).toBeVisible();
  });
});
