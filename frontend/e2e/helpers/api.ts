import type { APIRequestContext } from "@playwright/test";

import { API_URL, WEBHOOK_TOKEN, uniqueName } from "./config";

export interface Incident {
  id: number;
  alert_name: string;
  severity: string;
  status: string;
  namespace: string;
  resource_name: string;
  root_cause: string | null;
  confidence_score: number | null;
}

export interface PendingApproval {
  incident_id: number;
  alert_name: string;
  status: string;
  resource_name: string;
}

export async function login(
  request: APIRequestContext,
  username: string,
  password: string
): Promise<string> {
  const res = await request.post(`${API_URL}/v1/auth/login`, {
    form: { username, password },
  });
  if (!res.ok()) {
    throw new Error(`login failed: ${res.status()} ${await res.text()}`);
  }
  return ((await res.json()) as { access_token: string }).access_token;
}

function authHeader(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export interface FiringAlert {
  alertname: string;
  severity: string;
  namespace: string;
  resource: string;
  kind?: string;
}

/**
 * POST an Alertmanager "firing" notification. The backend returns immediately
 * and runs the agent pipeline in a background task, so callers must poll.
 */
export async function injectAlert(
  request: APIRequestContext,
  alert: FiringAlert
): Promise<void> {
  const labels: Record<string, string> = {
    alertname: alert.alertname,
    severity: alert.severity,
    namespace: alert.namespace,
    kind: alert.kind ?? "pod",
  };
  labels[alert.kind ?? "pod"] = alert.resource;

  const res = await request.post(`${API_URL}/v1/webhooks/alertmanager`, {
    headers: {
      Authorization: `Bearer ${WEBHOOK_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      version: "4",
      status: "firing",
      alerts: [
        {
          status: "firing",
          labels,
          annotations: { summary: `e2e injected ${alert.alertname}` },
        },
      ],
    },
  });
  if (!res.ok()) {
    throw new Error(`webhook failed: ${res.status()} ${await res.text()}`);
  }
}

export async function listIncidents(
  request: APIRequestContext,
  token: string,
  status?: string
): Promise<Incident[]> {
  const url = new URL(`${API_URL}/v1/incidents`);
  url.searchParams.set("limit", "200");
  if (status) url.searchParams.set("status", status);
  const res = await request.get(url.toString(), { headers: authHeader(token) });
  if (!res.ok()) throw new Error(`list incidents: ${res.status()}`);
  return (await res.json()) as Incident[];
}

export async function pendingApprovals(
  request: APIRequestContext,
  token: string
): Promise<PendingApproval[]> {
  const res = await request.get(`${API_URL}/v1/actions/pending`, {
    headers: authHeader(token),
  });
  if (!res.ok()) throw new Error(`pending: ${res.status()}`);
  return ((await res.json()) as { pending: PendingApproval[] }).pending;
}

/** Poll the API until `predicate` matches on the incident with `alertName`. */
export async function waitForIncident(
  request: APIRequestContext,
  token: string,
  alertName: string,
  predicate: (inc: Incident) => boolean,
  timeoutMs = 60_000
): Promise<Incident> {
  const deadline = Date.now() + timeoutMs;
  let last: Incident | undefined;
  while (Date.now() < deadline) {
    const incidents = await listIncidents(request, token);
    last = incidents.find((i) => i.alert_name === alertName);
    if (last && predicate(last)) return last;
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(
    `timed out waiting for incident '${alertName}'` +
      (last ? ` (last status=${last.status})` : " (never appeared)")
  );
}

/**
 * Inject a critical alert (SEV-1 always requires approval) and wait until it
 * is parked in the approvals queue. Returns the resource/alert names used.
 */
export async function seedPendingIncident(
  request: APIRequestContext,
  token: string
): Promise<{ alertName: string; resource: string; incidentId: number }> {
  const alertName = uniqueName("E2EPending");
  const resource = uniqueName("e2e-pod");
  await injectAlert(request, {
    alertname: alertName,
    severity: "critical",
    namespace: "sock-shop",
    resource,
  });
  const incident = await waitForIncident(
    request,
    token,
    alertName,
    (inc) => inc.status === "Awaiting Approval"
  );
  return { alertName, resource, incidentId: incident.id };
}
