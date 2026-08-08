"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { usePoll } from "@/components/usePoll";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Stats } from "@/lib/api";
import { formatSeconds } from "@/lib/format";

const SEV_COLORS: Record<string, string> = {
  "SEV-1": "#ef4444",
  "SEV-2": "#f97316",
  "SEV-3": "#eab308",
  "SEV-4": "#3b82f6",
}

const STATUS_COLORS = [
  "#3b82f6",
  "#a855f7",
  "#eab308",
  "#22c55e",
  "#ef4444",
  "#71717a",
  "#0ea5e9",
]

export default function AnalyticsPage() {
  const { data } = usePoll<Stats>(() => api.stats(), 30000)

  if (!data) {
    return <p className="text-sm text-muted-foreground">Loading analytics…</p>
  }

  const severityData = Object.entries(data.by_severity).map(([name, value]) => ({
    name,
    value,
  }))
  const statusData = Object.entries(data.by_status).map(([name, value]) => ({ name, value }))
  const trendData = data.last_7_days.map((d) => ({ date: d.date.slice(5), count: d.count }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground">Operational metrics across all incidents</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total incidents" value={String(data.total)} />
        <StatCard label="Resolved" value={String(data.resolved)} />
        <StatCard label="Resolved rate" value={`${(data.resolved_rate * 100).toFixed(0)}%`} />
        <StatCard label="Open (live)" value={String(data.open)} />
        <StatCard label="Avg MTTD" value={formatSeconds(data.avg_mttd_seconds)} />
        <StatCard label="Avg MTTR" value={formatSeconds(data.avg_mttr_seconds)} />
        <StatCard label="Escalated" value={String(data.escalated)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Incidents by severity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={severityData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="value" name="Incidents" radius={[4, 4, 0, 0]}>
                    {severityData.map((entry) => (
                      <Cell key={entry.name} fill={SEV_COLORS[entry.name] ?? "#71717a"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Incidents by status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label
                  >
                    {statusData.map((entry, i) => (
                      <Cell key={entry.name} fill={STATUS_COLORS[i % STATUS_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Detections — last 7 days</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" name="Detected" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  )
}
