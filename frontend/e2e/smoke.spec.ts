import { expect, test } from "@playwright/test";

import { CREDS } from "./helpers/config";
import { loginViaUI } from "./helpers/ui";

test.describe("smoke", () => {
  test("admin logs in and sees the incidents dashboard", async ({ page }) => {
    await loginViaUI(page, CREDS.admin.username, CREDS.admin.password);
    await expect(page.getByRole("heading", { name: "Incidents" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Approvals" })).toBeVisible();
    await expect(page.getByText(CREDS.admin.username, { exact: true })).toBeVisible();
  });

  test("navigates across all dashboard sections", async ({ page }) => {
    await loginViaUI(page, CREDS.admin.username, CREDS.admin.password);

    await page.getByRole("link", { name: "Analytics" }).click();
    await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();

    await page.getByRole("link", { name: "Cluster" }).click();
    await expect(page.getByRole("heading", { name: "Cluster" })).toBeVisible();

    await page.getByRole("link", { name: "Approvals" }).click();
    await expect(page.getByRole("heading", { name: "Approvals" })).toBeVisible();

    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  test("rejects invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill(CREDS.admin.username);
    await page.getByLabel("Password").fill("definitely-wrong");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByText(/incorrect username or password/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("logout returns to the login page", async ({ page }) => {
    await loginViaUI(page, CREDS.admin.username, CREDS.admin.password);
    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauthenticated visitor is redirected to login", async ({ page }) => {
    await page.goto("/incidents");
    await expect(page).toHaveURL(/\/login/);
  });
});
