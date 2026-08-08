"use client";

import { useState } from "react";

import { usePoll } from "@/components/usePoll";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ClusterPage() {
  const [ns, setNs] = useState("sock-shop")
  const { data, loading, error } = usePoll(() => api.pods(ns), 15000, ns)
  const pods = data?.pods ?? []

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold">Cluster</h1>
        <p className="text-sm text-muted-foreground">Pods visible to the Klarnova service account</p>
      </div>

      <div className="mb-4 max-w-xs">
        <label htmlFor="ns" className="mb-1 block text-sm font-medium">
          Namespace
        </label>
        <Input id="ns" value={ns} onChange={(e) => setNs(e.target.value)} />
      </div>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Pods</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && pods.length === 0 ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : pods.length === 0 ? (
            <p className="text-sm text-muted-foreground">No pods found in namespace “{ns}”.</p>
          ) : (
            <ul className="space-y-1">
              {pods.map((pod) => (
                <li
                  key={pod}
                  className="rounded-md px-2 py-1 font-mono text-sm hover:bg-muted/50"
                >
                  {pod}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
