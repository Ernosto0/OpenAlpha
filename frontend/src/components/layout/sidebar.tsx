import {
  BarChart3,
  FileClock,
  Gauge,
  PlayCircle,
  Settings,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { cn } from "../../lib/utils";

const navigation = [
  { label: "Dashboard", href: "/", icon: Gauge },
  { label: "Run analysis", href: "/analysis", icon: PlayCircle },
  { label: "Reports", href: "/reports", icon: FileClock },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="flex h-full w-full flex-col border-r border-border bg-card">
      <div className="flex h-16 items-center gap-3 border-b border-border px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground">
          OA
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">OpenAlpha</p>
          <p className="truncate text-xs text-muted-foreground">Equity research</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => (
          <NavLink
            className={({ isActive }) =>
              cn(
                "flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground",
                isActive && "bg-muted text-foreground",
              )
            }
            end={item.href === "/"}
            key={item.href}
            to={item.href}
          >
            <item.icon className="h-4 w-4" aria-hidden="true" />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-4">
        <div className="flex items-center gap-3 rounded-md bg-muted px-3 py-3">
          <BarChart3 className="h-4 w-4 text-primary" aria-hidden="true" />
          <div className="min-w-0">
            <p className="truncate text-xs font-medium">Local workspace</p>
            <p className="truncate text-xs text-muted-foreground">API on port 8000</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
