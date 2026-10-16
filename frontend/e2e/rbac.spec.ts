import { expect, test } from "@playwright/test";

import { login as apiLogin, seedPendingIncident } from "./helpers/api";
import { CREDS } from "./helpers/config";
import { loginViaUI } from "./helpers/ui";

test.describe("rbac", () => {
  test("viewer does not see the Settings nav item and cannot approve", async ({
    page,
    request,
  }) => {
    const adminToken = await apiLogin(
      request,
      CREDS.admin.username,
      CREDS.admin.password
    );
    const { alertName } = await seedPendingIncident(request, adminToken);

    await loginViaUI(page, CREDS.viewer.username, CREDS.viewer.password);

    await expect(page.getByRole("link", { name: "Settings" })).toHaveCount(0);

    await page.getByRole("link", { name: "Approvals" }).click();
    const card = page
      .locator('[data-slot="card"]')
      .filter({ hasText: alertName });
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.getByRole("button", { name: "Approve" })).toBeDisabled();
    await expect(card.getByRole("button", { name: "Reject" })).toBeDisabled();
    await expect(
      card.getByText(/read-only: only admin\/engineer roles can approve/i)
    ).toBeVisible();
  });

  test("viewer sees the settings page in read-only mode", async ({ page }) => {
    await loginViaUI(page, CREDS.viewer.username, CREDS.viewer.password);
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    await expect(
      page.getByText(/read-only: only the admin role can change policy rules/i)
    ).toBeVisible();
    await expect(page.locator('select[aria-label="restart_pod sev_4"]')).toHaveCount(0);
  });

  test("engineer can approve but not change policy", async ({ page, request }) => {
    const adminToken = await apiLogin(
      request,
      CREDS.admin.username,
      CREDS.admin.password
    );
    const { alertName } = await seedPendingIncident(request, adminToken);

    await loginViaUI(page, CREDS.engineer.username, CREDS.engineer.password);
    await page.getByRole("link", { name: "Approvals" }).click();

    const card = page
      .locator('[data-slot="card"]')
      .filter({ hasText: alertName });
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.getByRole("button", { name: "Approve" })).toBeEnabled();

    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    // Only admins get editable policy selects.
    await expect(page.locator('select[aria-label="restart_pod sev_4"]')).toHaveCount(0);
  });
});
