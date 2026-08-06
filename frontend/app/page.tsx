const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HealthResponse = {
  status: string;
  service: string;
};

async function getBackendHealth(): Promise<
  { ok: true; data: HealthResponse } | { ok: false; error: string }
> {
  try {
    const res = await fetch(`${API_URL}/api/v1/health`, { cache: "no-store" });
    if (!res.ok) {
      return { ok: false, error: `Backend responded ${res.status}` };
    }
    return { ok: true, data: await res.json() };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Unknown error" };
  }
}

export default async function Home() {
  const health = await getBackendHealth();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-semibold">Klarnova</h1>
      <p className="text-sm text-neutral-400">Frontend ↔ backend health round-trip (KLR-A7)</p>
      {health.ok ? (
        <div className="rounded-lg border border-green-700 bg-green-950/40 px-4 py-3 text-sm">
          <span className="font-mono text-green-400">{health.data.status}</span>
          {" — "}
          {health.data.service}
        </div>
      ) : (
        <div className="rounded-lg border border-red-700 bg-red-950/40 px-4 py-3 text-sm">
          Could not reach backend at <span className="font-mono">{API_URL}</span>: {health.error}
        </div>
      )}
    </main>
  );
}
