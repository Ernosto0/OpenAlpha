import { Menu, Search } from "lucide-react";
import { useState } from "react";
import { Outlet } from "react-router-dom";

import { getProviderLabel } from "../../lib/analysis";
import { useAppSettings } from "../../lib/settings-context";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Sidebar } from "./sidebar";

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { settings } = useAppSettings();
  const providerLabel = settings ? getProviderLabel(settings.default_provider) : "Loading";
  const modelLabel = settings?.default_model ?? "...";

  return (
    <div className="min-h-screen bg-background text-foreground lg:grid lg:grid-cols-[260px_1fr]">
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {sidebarOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
            type="button"
          />
          <div className="relative h-full w-[260px]">
            <Sidebar />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-col">
        {/* Top Command / Search Bar */}
        <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-border bg-background px-4 lg:px-8">
          <Button
            aria-label="Open navigation"
            className="lg:hidden"
            onClick={() => setSidebarOpen(true)}
            size="icon"
            variant="ghost"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </Button>

          <div className="flex flex-1 items-center gap-4">
            <div className="relative w-full max-w-md hidden sm:block">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="search"
                placeholder="Search symbol... AAPL, MSFT, NVDA"
                className="w-full bg-card pl-9 border-border text-sm shadow-none focus-visible:ring-1 focus-visible:ring-primary"
              />
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
            <div className="hidden md:flex items-center gap-1.5">
              <span className="text-foreground">PRV:</span>
              <span>{providerLabel}</span>
            </div>
            <div className="hidden md:flex items-center gap-1.5">
              <span className="text-foreground">MOD:</span>
              <span>{modelLabel}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-foreground">CST:</span>
              <span>$0.04</span>
            </div>
          </div>
        </header>

        <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
