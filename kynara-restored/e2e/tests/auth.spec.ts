import { expect, test } from "@playwright/test";

test.describe("authentication", () => {
  test("logs in with seeded admin credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("admin@acme.com");
    await page.getByLabel(/password/i).fill("demo-password-123!");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/app\/dashboard/);
    await expect(page.getByText(/decisions today/i)).toBeVisible();
  });

  test("rejects bad credentials and stays on /login", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("admin@acme.com");
    await page.getByLabel(/password/i).fill("wrong-password");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText(/invalid credentials/i)).toBeVisible();
  });
});
