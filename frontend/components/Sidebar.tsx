"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, BarChart3, Boxes, CheckSquare, LogOut, Settings } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/incidents", label: "Incidents", icon: Activity },
  { href: "/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/cluster", label: "Cluster", icon: Boxes },
]

const SETTINGS_ITEM = { href: "/settings", label: "Settings", icon: Settings }

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuth()

  const nav = user?.role === "Admin" || user?.role === "Engineer"
    ? [...NAV, SETTINGS_ITEM]
    : NAV

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r bg-muted/40">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <Activity className="size-5 text-primary" />
        <span className="text-sm font-semibold">Klarnova</span>
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-3">
        {nav.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <item.icon className="size-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="border-t p-3">
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{user?.username}</p>
            <p className="text-xs capitalize text-muted-foreground">{user?.role}</p>
          </div>
          <button
            type="button"
            aria-label="Log out"
            onClick={() => {
              logout()
              router.replace("/login")
            }}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}
