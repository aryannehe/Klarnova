export const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
export const WEBHOOK_TOKEN =
  process.env.ALERTMANAGER_WEBHOOK_TOKEN ?? "e2e-token";

export const CREDS = {
  admin: { username: "admin", password: "admin123" },
  engineer: { username: "engineer", password: "engineer123" },
  viewer: { username: "viewer", password: "viewer123" },
} as const;

let counter = 0;

/** Unique resource/alert suffix so incidents from different tests never dedup. */
export function uniqueName(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now().toString(36)}-${counter}`;
}
