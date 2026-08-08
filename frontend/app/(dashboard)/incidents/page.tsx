"use client";

import Link from "next/link";
import { useState } from "react";

import { usePoll } from "@/components/usePoll";
import { SeverityBadge, StatusBadge } from "@/components/StatusBadge";
import { api, type Incident } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUSES = [
  "",
  "Open",
  "Investigating",
  "Awaiting Approval",
  "Remediating",
  "Resolved",
  "Escalated",
  "Closed",
]

export default function IncidentsPage() {
  const [status, setStatus] = useState("")
  const { data, loading, error } = usePoll<Incident[]>(
    () => api.incidents(status || undefined),
    15000,
    status
  )
  const incidents = data ?? []

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Incidents</h1>
          <p className="text-sm text-muted-foreground">
            Live feed from Alertmanager webhooks (refreshes automatically)
          </p>
        </div>
        <div className="flex flex-wrap gap-1">
          {STATUSES.map((s) => (
            <button
              key={s || "all"}
              type="button"
              onClick={() => setStatus(s)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                status === s
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/70"
              )}
            >
              {s || "All"}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-2">#</th>
              <th className="px-4 py-2">Alert</th>
              <th className="px-4 py-2">Severity</th>
              <th className="px-4 py-2">Priority</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Resource</th>
              <th className="px-4 py-2">Detected</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((inc) => (
              <tr key={inc.id} className="border-b last:border-0 hover:bg-muted/40">
                <td className="px-4 py-2 font-mono text-xs">{inc.id}</td>
                <td className="px-4 py-2">
                  <Link
                    href={`/incidents/${inc.id}`}
                    className="font-medium text-primary hover:underline"
                  >
                    {inc.alert_name}
                  </Link>
                </td>
                <td className="px-4 py-2">
                  <SeverityBadge severity={inc.severity} />
                </td>
                <td className="px-4 py-2">{inc.priority}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={inc.status} />
                </td>
                <td className="px-4 py-2">
                  <span className="font-mono text-xs">{inc.resource_name}</span>
                  <span className="text-xs text-muted-foreground"> ({inc.namespace})</span>
                </td>
                <td className="px-4 py-2 text-muted-foreground">{formatDate(inc.detected_at)}</td>
              </tr>
            ))}
            {incidents.length === 0 && !loading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                  No incidents{status ? ` with status "${status}"` : ""} yet.
                </td>
              </tr>
            )}
            {loading && incidents.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                  Loading…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
