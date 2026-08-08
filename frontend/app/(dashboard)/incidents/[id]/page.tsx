"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { SeverityBadge, StatusBadge } from "@/components/StatusBadge";
import { api, type Trace } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatConfidence, formatDate, formatSeconds } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>()
  const id = params.id
  const { canApprove } = useAuth()

  const [trace, setTrace] = useState<Trace | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setTrace(await api.trace(id))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const t = await api.trace(id)
        if (!cancelled) {
          setTrace(t)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [id])

  const decide = async (approved: boolean) => {
    if (!trace) return
    const selected = trace.selected_action
    if (!selected?.action_type) return
    setBusy(true)
    try {
      await api.approve({
        incident_id: String(trace.incident.id),
        action_type: selected.action_type,
        approved,
        target_resource: selected.target_resource,
        namespace: selected.namespace,
      })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (error && !trace) return <p className="text-sm text-destructive">{error}</p>
  if (!trace) return null

  const inc = trace.incident
  const pending = trace.requires_approval && inc.status === "Awaiting Approval"
  const selected = trace.selected_action

  return (
    <div className="mx-auto max-w-4xl">
      <Link
        href="/incidents"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to incidents
      </Link>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      <Card className="mb-4">
        <CardHeader className="flex-row items-center justify-between">
          <div className="flex flex-col gap-1">
            <CardTitle className="text-lg">
              #{inc.id} · {inc.alert_name}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              {inc.resource_kind} <span className="font-mono">{inc.resource_name}</span> in{" "}
              {inc.namespace}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <SeverityBadge severity={inc.severity} />
            <StatusBadge status={inc.status} />
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Priority</p>
            <p className="font-medium">{inc.priority}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Detected</p>
            <p className="font-medium">{formatDate(inc.detected_at)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Confidence</p>
            <p className="font-medium">{formatConfidence(inc.confidence_score)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Resolved</p>
            <p className="font-medium">{formatDate(inc.remediated_at)}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Root cause</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm">{inc.root_cause ?? "Not diagnosed"}</p>
        </CardContent>
      </Card>

      {pending && selected?.action_type && (
        <Card className="mb-4 border-amber-500/40">
          <CardHeader>
            <CardTitle>Awaiting approval</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4 text-sm">
              Proposed action:{" "}
              <span className="font-mono font-medium">{selected.action_type}</span> on{" "}
              <span className="font-mono">{selected.target_resource ?? inc.resource_name}</span>
              {selected.namespace ? ` (${selected.namespace})` : ""} · proposed by{" "}
              {selected.source}
            </p>
            <div className="flex gap-2">
              <Button
                variant="default"
                disabled={!canApprove || busy}
                onClick={() => void decide(true)}
              >
                Approve & remediate
              </Button>
              <Button
                variant="destructive"
                disabled={!canApprove || busy}
                onClick={() => void decide(false)}
              >
                Reject
              </Button>
              {!canApprove && (
                <p className="self-center text-xs text-muted-foreground">
                  Only admin/engineer roles can approve.
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Agent trace</CardTitle>
        </CardHeader>
        <CardContent>
          {trace.agent_runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No agent runs recorded.</p>
          ) : (
            <ol className="relative space-y-4 border-l pl-4">
              {trace.agent_runs.map((run, i) => (
                <li key={i} className="relative">
                  <span className="absolute -left-[21px] top-1.5 size-2.5 rounded-full bg-primary" />
                  <p className="text-sm font-medium">{run.agent}</p>
                  <p className="text-sm text-muted-foreground">
                    {extractSummary(run.outputs)}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      {trace.remediations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Remediations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {trace.remediations.map((r, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm"
              >
                <span>
                  <span className="font-mono">{r.action}</span>{" "}
                  <span className="text-muted-foreground">({r.category})</span>
                </span>
                <span className="flex items-center gap-3">
                  <StatusBadge status={r.outcome} />
                  <span className="text-muted-foreground">
                    {formatSeconds(r.time_to_resolve)}
                  </span>
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function extractSummary(outputs: unknown): string {
  if (!outputs || typeof outputs !== "object") return ""
  const o = outputs as Record<string, unknown>
  const content = o.content
  if (typeof content === "string") return content
  const msg = o.message
  if (msg && typeof msg === "object") {
    const m = msg as Record<string, unknown>
    if (typeof m.content === "string") return m.content
  }
  return JSON.stringify(outputs).slice(0, 200)
}
