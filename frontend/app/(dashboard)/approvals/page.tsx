"use client";

import { useState } from "react";
import Link from "next/link";

import { SeverityBadge } from "@/components/StatusBadge";
import { usePoll } from "@/components/usePoll";
import { api, type PendingApproval } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatConfidence, formatDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ApprovalsPage() {
  const { canApprove } = useAuth()
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { data, refetch } = usePoll(() => api.pending(), 10000)
  const queue = data?.pending ?? []

  const decide = async (item: PendingApproval, approved: boolean) => {
    const selected = item.selected_action
    if (!selected?.action_type) return
    setBusyId(item.incident_id)
    setError(null)
    try {
      await api.approve({
        incident_id: String(item.incident_id),
        action_type: selected.action_type,
        approved,
        target_resource: selected.target_resource,
        namespace: selected.namespace,
      })
      await refetch()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold">Approvals</h1>
        <p className="text-sm text-muted-foreground">
          High-risk remediations awaiting an operator decision
        </p>
      </div>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      {queue.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No incidents awaiting approval.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {queue.map((item) => {
            const selected = item.selected_action
            return (
              <Card key={item.incident_id} className="border-amber-500/40">
                <CardHeader className="flex-row items-start justify-between">
                  <div className="flex flex-col gap-1">
                    <CardTitle className="text-base">
                      #{item.incident_id} ·{" "}
                      <Link
                        href={`/incidents/${item.incident_id}`}
                        className="text-primary hover:underline"
                      >
                        {item.alert_name}
                      </Link>
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {item.resource_kind} <span className="font-mono">{item.resource_name}</span>{" "}
                      in {item.namespace} · detected {formatDate(item.detected_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={item.severity} />
                    <span className="text-xs text-muted-foreground">{item.priority}</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="mb-3 rounded-lg bg-muted/50 px-3 py-2 text-sm">
                    <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                      Root cause
                    </p>
                    <p>{item.root_cause ?? "Not diagnosed"}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Confidence {formatConfidence(item.confidence_score)}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm">
                      Proposed action:{" "}
                      <span className="font-mono font-medium">
                        {selected.action_type ?? "none"}
                      </span>{" "}
                      on <span className="font-mono">{selected.target_resource ?? "—"}</span>
                      {selected.namespace ? ` (${selected.namespace})` : ""} · from{" "}
                      {selected.source}
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="default"
                        disabled={!canApprove || busyId === item.incident_id}
                        onClick={() => void decide(item, true)}
                      >
                        Approve
                      </Button>
                      <Button
                        variant="destructive"
                        disabled={!canApprove || busyId === item.incident_id}
                        onClick={() => void decide(item, false)}
                      >
                        Reject
                      </Button>
                    </div>
                  </div>
                  {!canApprove && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Read-only: only admin/engineer roles can approve or reject.
                    </p>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
