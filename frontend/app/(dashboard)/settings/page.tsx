"use client";

import { useState } from "react";

import { usePoll } from "@/components/usePoll";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type KnowledgeDoc } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/format";

const SEV_KEYS = ["sev_4", "sev_3", "sev_2", "sev_1"] as const;
const SEV_LABELS: Record<string, string> = {
  sev_1: "SEV-1",
  sev_2: "SEV-2",
  sev_3: "SEV-3",
  sev_4: "SEV-4",
  default: "default",
};

export default function SettingsPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === "Admin"
  const [saving, setSaving] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const policy = usePoll(() => api.policy(), 30000)
  const sources = usePoll(() => api.knowledgeSources(), 60000)
  const docs = usePoll(() => api.knowledgeDocs(), 30000)

  const changeMode = async (action: string, severity: string, mode: "auto" | "require_approval") => {
    setSaving(`${action}:${severity}`)
    setMsg(null)
    setErr(null)
    try {
      await api.updatePolicyRule({ action, severity, execution_mode: mode })
      await policy.refetch()
      setMsg(`Policy updated: ${action} @ ${SEV_LABELS[severity] ?? severity} → ${mode}`)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(null)
    }
  }

  const refresh = async () => {
    setMsg(null)
    setErr(null)
    try {
      const res = await api.refreshKnowledge()
      await docs.refetch()
      setMsg(`Knowledge base refreshed: ${res.added} document(s) added/replaced`)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const rules = policy.data?.actions ?? {}

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Risk policy and knowledge-base administration
        </p>
      </div>

      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {err && <p className="text-sm text-destructive">{err}</p>}
      {!isAdmin && (
        <p className="text-sm text-muted-foreground">
          Read-only: only the admin role can change policy rules or refresh the knowledge base.
        </p>
      )}

      <Card>
        <CardHeader className="flex-row items-start justify-between">
          <div>
            <CardTitle className="text-base">Risk policy</CardTitle>
            <p className="text-sm text-muted-foreground">
              Execution mode per action and severity. Confidence threshold:{" "}
              {policy.data?.confidence_threshold ?? "—"}
            </p>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2">Action</th>
                  {SEV_KEYS.map((sev) => (
                    <th key={sev} className="px-3 py-2">
                      {SEV_LABELS[sev]}
                    </th>
                  ))}
                  <th className="px-3 py-2">default</th>
                </tr>
              </thead>
              <tbody>
                {policy.data?.whitelist.map((action) => {
                  const rule = rules[action] ?? {}
                  return (
                    <tr key={action} className="border-b last:border-0">
                      <td className="px-3 py-2 font-mono">{action}</td>
                      {[...SEV_KEYS, "default"].map((sev) => {
                        const value = (rule[sev] ?? rule.default ?? "deny") as string
                        return (
                          <td key={sev} className="px-3 py-2">
                            {isAdmin ? (
                              <select
                                aria-label={`${action} ${sev}`}
                                value={value}
                                disabled={saving === `${action}:${sev}`}
                                onChange={(e) =>
                                  void changeMode(
                                    action,
                                    sev,
                                    e.target.value as "auto" | "require_approval"
                                  )
                                }
                                className="rounded-md border bg-background px-2 py-1 text-xs"
                              >
                                <option value="auto">auto</option>
                                <option value="require_approval">approval</option>
                                <option value="deny">deny</option>
                              </select>
                            ) : (
                              <span className="text-xs">{value}</span>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {policy.error && (
            <p className="mt-2 text-sm text-destructive">{policy.error}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-start justify-between">
          <div>
            <CardTitle className="text-base">Knowledge base</CardTitle>
            <p className="text-sm text-muted-foreground">
              {sources.data?.path ?? "sources.yaml"}
            </p>
          </div>
          {isAdmin && (
            <Button variant="outline" size="sm" onClick={() => void refresh()}>
              Re-ingest sources
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.entries(docs.data?.collections ?? {}).map(([name, count]) => (
              <div key={name} className="rounded-lg bg-muted/50 px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  {name}
                </p>
                <p className="text-lg font-semibold">{count}</p>
              </div>
            ))}
          </div>

          {Object.entries(sources.data?.collections ?? {}).map(([collection, entries]) => (
            <div key={collection}>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {collection} · {entries.length}
              </p>
              <ul className="space-y-1">
                {entries.map((entry) => (
                  <li
                    key={`${collection}:${entry.id}`}
                    className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-1.5 text-sm"
                  >
                    <span className="font-mono">{entry.id}</span>
                    <span className="text-muted-foreground">{entry.title}</span>
                    <span className="text-xs text-muted-foreground">{entry.source}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {docs.data && docs.data.count > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Ingested docs ({docs.data.count})
              </p>
              <div className="max-h-56 space-y-1 overflow-y-auto">
                {docs.data.docs.map((doc: KnowledgeDoc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-1.5 text-sm"
                  >
                    <span className="font-mono text-xs">{doc.source_url}</span>
                    <span className="text-xs text-muted-foreground">{doc.doc_type}</span>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(doc.last_ingested)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {docs.error && <p className="text-sm text-destructive">{docs.error}</p>}
        </CardContent>
      </Card>
    </div>
  )
}
