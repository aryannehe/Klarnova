import { expect, test } from "@playwright/test";

import {
  injectAlert,
  listIncidents,
  seedPendingIncident,
  waitForIncident,
  login as apiLogin,
} from "./helpers/api";
import { CREDS, uniqueName } from "./helpers/config";
import { loginViaUI } from "./helpers/ui";

test.describe("incident flow", () => {
  test("a webhook alert surfaces as an incident with a diagnosis", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(
      request,
      CREDS.admin.username,
      CREDS.admin.password
    );
    const alertName = uniqueName("E2ETrace");
    const resource = uniqueName("e2e-pod");

    await injectAlert(request, {
      alertname: alertName,
      severity: "critical",
      namespace: "sock-shop",
      resource,
    });
    await waitForIncident(request, token, alertName, (inc) => inc.status !== "Investigating");

    await loginViaUI(page, CREDS.admin.username, CREDS.admin.password);

    const row = page.getByRole("row").filter({ hasText: alertName });
    await expect(row).toBeVisible({ timeout: 30_000 });
    await row.getByRole("link", { name: alertName }).click();

    await expect(page).toHaveURL(/\/incidents\/\d+/);
    await expect(
      page.getByText(new RegExp(`#\\d+ · ${alertName}`)).first()
    ).toBeVisible();
    await expect(page.getByText("Root cause", { exact: true })).toBeVisible();
    await expect(page.getByText("Agent trace", { exact: true })).toBeVisible();
  });

  test("an operator approves a pending remediation from the queue", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(
      request,
      CREDS.admin.username,
      CREDS.admin.password
    );
    const { alertName, incidentId } = await seedPendingIncident(request, token);

    await loginViaUI(page, CREDS.admin.username, CREDS.admin.password);
    await page.getByRole("link", { name: "Approvals" }).click();
    await expect(
      page.getByRole("heading", { name: "Approvals" })
    ).toBeVisible();

    const card = page
      .locator('[data-slot="card"]')
      .filter({ hasText: alertName });
    await expect(card).toBeVisible({ timeout: 30_000 });
    await card.getByRole("button", { name: "Approve" }).click();

    // The queue refetches after the decision: the card should leave the queue.
    await expect(card).toHaveCount(0, { timeout: 30_000 });

    await expect
      .poll(async () => {
        const incidents = await listIncidents(request, token);
        return incidents.find((i) => i.id === incidentId)?.status;
      })
      .not.toBe("Awaiting Approval");
  });

  test("a rejected remediation leaves the approval queue and is not resolved", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(
      request,
      CREDS.admin.username,
      CREDS.admin.password
    );
    const { alertName, incidentId } = await seedPendingIncident(request, token);

    await loginViaUI(page, CREDS.admin.username, CREDS.admin.password);
    await page.goto("/approvals");

    const card = page
      .locator('[data-slot="card"]')
      .filter({ hasText: alertName });
    await expect(card).toBeVisible({ timeout: 30_000 });
    await card.getByRole("button", { name: "Reject" }).click();
    await expect(card).toHaveCount(0, { timeout: 30_000 });

    await expect
      .poll(async () => {
        const incidents = await listIncidents(request, token);
        return incidents.find((i) => i.id === incidentId)?.status;
      })
      .not.toBe("Awaiting Approval");
  });
});
