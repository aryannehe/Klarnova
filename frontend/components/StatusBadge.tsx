import { cn } from "@/lib/utils"

const severityStyles: Record<string, string> = {
  "SEV-1": "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400",
  "SEV-2": "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-400",
  "SEV-3": "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-400",
  "SEV-4": "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400",
}

const statusStyles: Record<string, string> = {
  Open: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/15 dark:text-zinc-300",
  Investigating: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400",
  "Awaiting Approval":
    "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400",
  Remediating: "bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-400",
  Resolved: "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-400",
  Escalated: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400",
  Closed: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/15 dark:text-zinc-300",
}

function BadgeChip({ label, className }: { label: string; className: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-semibold",
        className
      )}
    >
      {label}
    </span>
  )
}

export function SeverityBadge({ severity }: { severity: string }) {
  const key = severity.toUpperCase()
  return (
    <BadgeChip label={severity} className={severityStyles[key] ?? "bg-zinc-100 text-zinc-600 dark:bg-zinc-500/15 dark:text-zinc-400"} />
  )
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <BadgeChip
      label={status}
      className={statusStyles[status] ?? "bg-zinc-100 text-zinc-600 dark:bg-zinc-500/15 dark:text-zinc-400"}
    />
  )
}
