import {
  Activity,
  Database,
  FileClock,
  Gauge,
  LineChart,
  PlayCircle,
  Settings,
  TerminalSquare,
  Wifi,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { cn } from "../../lib/utils";

const navigation = [
  { label: "Dashboard", href: "/", icon: Gauge },
  { label: "Run analysis", href: "/analysis", icon: PlayCircle },
  { label: "Reports", href: "/reports", icon: FileClock },
  { label: "Performance", href: "/performance", icon: LineChart },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="flex h-full w-full flex-col border-r border-border bg-card">
      <div className="flex h-14 items-center gap-3 border-b border-border px-5">
        <div className="flex items-center justify-center text-primary">
          <TerminalSquare className="h-6 w-6" strokeWidth={2} />
        </div>
        <div className="min-w-0 flex items-baseline gap-1">
          <p className="truncate text-base font-bold tracking-tight">OpenAlpha</p>
          <span className="text-primary font-mono text-sm">α_</span>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => (
          <NavLink
            className={({ isActive }) =>
              cn(
                "flex h-9 items-center gap-3 rounded-md px-3 text-sm font-medium text-muted-foreground transition hover:bg-muted/50 hover:text-foreground",
                isActive && "bg-muted text-primary font-semibold",
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

      <div className="border-t border-border p-4 space-y-3">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Activity className="h-3 w-3" />
              <span>Localhost</span>
            </div>
            <span className="text-success">OK</span>
          </div>
          
          <div className="flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Database className="h-3 w-3" />
              <span>SQLite</span>
            </div>
            <span className="text-success">CONN</span>
          </div>

          <div className="flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Wifi className="h-3 w-3" />
              <span>Provider API</span>
            </div>
            <span className="text-success">200ms</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
