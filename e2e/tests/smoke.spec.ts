import { test, expect } from "@playwright/test";

test.describe("Production smoke tests", () => {
  test("frontend loads", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBe(200);
  });

  test("login page renders", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("form")).toBeVisible({ timeout: 10_000 });
  });

  test("API health check", async ({ request }) => {
    const baseUrl =
      process.env.API_URL || "https://imperecta-production.up.railway.app";
    const resp = await request.get(`${baseUrl}/api/health`);
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data.status).toBe("ok");
  });

  test("API docs accessible", async ({ request }) => {
    const baseUrl =
      process.env.API_URL || "https://imperecta-production.up.railway.app";
    const resp = await request.get(`${baseUrl}/docs`);
    expect(resp.status()).toBe(200);
  });
});
