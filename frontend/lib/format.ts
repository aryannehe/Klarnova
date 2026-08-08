export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "\u2014";
  return d.toLocaleString();
}

export function formatSeconds(sec: number | null | undefined): string {
  if (sec == null || Number.isNaN(sec)) return "\u2014";
  if (sec < 60) return `${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function formatConfidence(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "\u2014";
  return `${Math.round(v * 100)}%`;
}
