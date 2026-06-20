import { Menu } from "lucide-react";
import { useState } from "react";
import { Outlet } from "react-router-dom";

import { Button } from "../ui/button";
import { Sidebar } from "./sidebar";

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background lg:grid lg:grid-cols-[260px_1fr]">
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {sidebarOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-foreground/25"
            onClick={() => setSidebarOpen(false)}
            type="button"
          />
          <div className="relative h-full w-[260px]">
            <Sidebar />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur lg:hidden">
          <Button
            aria-label="Open navigation"
            onClick={() => setSidebarOpen(true)}
            size="icon"
            variant="secondary"
          >
            <Menu className="h-4 w-4" aria-hidden="true" />
          </Button>
          <div>
            <p className="text-sm font-semibold">OpenAlpha</p>
            <p className="text-xs text-muted-foreground">Equity research</p>
          </div>
        </header>

        <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
