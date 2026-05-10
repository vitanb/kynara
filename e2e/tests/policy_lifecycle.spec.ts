import { expect, test } from "@playwright/test";

const ADMIN = { email: "admin@acme.com", password: "demo-password-123!" };

async function login(page: any) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(ADMIN.email);
  await page.getByLabel(/password/i).fill(ADMIN.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL(/\/app\/dashboard/);
}

test("admin can create a policy and simulate it", async ({ page }) => {
  await login(page);
  await page.goto("/app/policies");
  await page.getByRole("link", { name: /new policy/i }).click();

  const slug = `e2e-deny-test-${Date.now()}`;
  await page.getByLabel(/slug/i).fill(slug);
  await page.getByLabel(/display name/i).fill("E2E deny test");
  await page.getByLabel(/effect/i).selectOption("deny");
  await page.getByLabel(/^actions/i).fill("crm.contacts.read");
  await page.getByRole("button", { name: /save/i }).click();

  await expect(page).toHaveURL(/\/app\/policies/);
  await expect(page.getByText(slug)).toBeVisible();

  // Simulate
  await page.getByText(slug).click();
  await page.getByRole("button", { name: /run simulation/i }).click();
  await expect(page.locator(".pill-danger")).toBeVisible();
});

test("audit chain verify shows 'verified' for an untouched chain", async ({ page }) => {
  await login(page);
  await page.goto("/app/audit");
  await page.getByRole("button", { name: /verify chain/i }).click();
  await expect(page.getByText(/chain verified/i)).toBeVisible();
});

test("agent kill switch flips status and produces an audit event", async ({ page }) => {
  await login(page);
  await page.goto("/app/agents");
  await page.getByText("CRM Assistant").click();
  await page.getByRole("button", { name: /kill/i }).click();
  await page.getByRole("button", { name: /confirm/i }).click();
  await expect(page.getByText(/disabled/i)).toBeVisible();

  await page.goto("/app/audit");
  await expect(page.getByText("agent.kill")).toBeVisible();
});
