import { expect, test } from "@playwright/test";

import { CREDS } from "./helpers/config";
import { loginViaUI } from "./helpers/ui";

test.describe("policy administration", () => {
  test("admin can change an action's execution mode and it persists", async ({
    page,
  }) => {
    await loginViaUI(page, CREDS.admin.username, CREDS.admin.password);
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

    const select = page.locator('select[aria-label="restart_pod sev_4"]');
    await expect(select).toBeVisible({ timeout: 30_000 });

    const original = await select.inputValue();
    const target = original === "require_approval" ? "auto" : "require_approval";

    try {
      await select.selectOption(target);
      await expect(
        page.getByText(new RegExp(`Policy updated: restart_pod @ SEV-4`))
      ).toBeVisible();

      // Reload and confirm the change was persisted server-side.
      await page.reload();
      await expect(
        page.locator('select[aria-label="restart_pod sev_4"]')
      ).toHaveValue(target);
    } finally {
      // Restore so other specs see the default policy.
      const restore = page.locator('select[aria-label="restart_pod sev_4"]');
      await restore.selectOption(original);
      await expect(
        page.locator('select[aria-label="restart_pod sev_4"]')
      ).toHaveValue(original);
    }
  });

  test("admin sees the knowledge base administration controls", async ({ page }) => {
    await loginViaUI(page, CREDS.admin.username, CREDS.admin.password);
    await page.goto("/settings");
    await expect(page.getByText("Risk policy", { exact: true })).toBeVisible();
    await expect(page.getByText("Knowledge base", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /re-ingest sources/i })
    ).toBeVisible();
  });
});
