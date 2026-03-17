import { test, expect } from "@playwright/test";

/**
 * Security-focused e2e tests.
 * Run against local dev: BASE_URL=http://localhost:5173 npx playwright test e2e/tests/security.spec.ts
 */

test.describe("Security - protected routes", () => {
  test("unauthenticated access to dashboard redirects to login", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await page.waitForURL(/login|dashboard/, { timeout: 5000 });
    const url = page.url();
    expect(url).toMatch(/login/);
  });

  test("unauthenticated access to products redirects to login", async ({
    page,
  }) => {
    await page.goto("/products");
    await page.waitForURL(/login|products/, { timeout: 5000 });
    const url = page.url();
    expect(url).toMatch(/login/);
  });

  test("admin page requires superuser - direct URL", async ({ page }) => {
    await page.goto("/admin");
    await page.waitForURL(/login|admin|dashboard/, { timeout: 5000 });
    const url = page.url();
    if (url.includes("/admin")) {
      await expect(
        page.locator("text=Superuser|403|Forbidden|Access denied")
      ).toBeVisible({ timeout: 3000 });
    }
  });
});

test.describe("Security - redirect handling", () => {
  const REDIRECT_TEST_EMAIL = `redirect_${Date.now()}@test.com`;
  const REDIRECT_TEST_PASSWORD = "RedirectTest123!";

  test("after login with javascript: next param, redirects to safe path not javascript:", async ({
    page,
  }) => {
    await page.goto("/register");
    await page.fill('input[name="name"], input[placeholder*="name" i]', "Redirect Test");
    await page.fill('input[type="email"], input[name="email"]', REDIRECT_TEST_EMAIL);
    await page.fill('input[type="password"]', REDIRECT_TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard|login/, { timeout: 10_000 });

    await page.goto("/login?next=javascript:alert(1)");
    await page.fill('input[type="email"], input[name="email"]', REDIRECT_TEST_EMAIL);
    await page.fill('input[type="password"]', REDIRECT_TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard|login/, { timeout: 10_000 });
    const url = page.url();
    expect(url).not.toMatch(/javascript:/);
  });

  test("after login with data: next param, redirects to safe path not data:", async ({
    page,
  }) => {
    const email = `data_redirect_${Date.now()}@test.com`;
    await page.goto("/register");
    await page.fill('input[name="name"], input[placeholder*="name" i]', "Data Redirect Test");
    await page.fill('input[type="email"], input[name="email"]', email);
    await page.fill('input[type="password"]', REDIRECT_TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard|login/, { timeout: 10_000 });

    await page.goto("/login?next=data:text/html,<script>alert(1)</script>");
    await page.fill('input[type="email"], input[name="email"]', email);
    await page.fill('input[type="password"]', REDIRECT_TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard|login/, { timeout: 10_000 });
    const url = page.url();
    expect(url).not.toMatch(/data:/);
  });
});

test.describe("Security - XSS resistance", () => {
  test("login page does not execute script in email field", async ({
    page,
  }) => {
    await page.goto("/login");
    const emailInput = page.locator(
      'input[type="email"], input[name="email"]'
    ).first();
    await emailInput.fill('<img src=x onerror="window.__xss=1">');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(1000);
    const xss = await page.evaluate(() => (window as unknown as { __xss?: number }).__xss);
    expect(xss).toBeUndefined();
  });
});
