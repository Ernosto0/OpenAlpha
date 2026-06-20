import {
  Activity,
  CheckCircle2,
  Clock3,
  Server,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { buttonVariants } from "../components/ui/button-styles";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { api, type HealthResponse } from "../lib/api";

export function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getHealth()
      .then(setHealth)
      .catch(() => setHealthError("API unavailable"));
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="Dashboard"
        title="Research workspace"
        description="Track provider readiness, recent analysis activity, and local API status."
        actions={
          <Link
            className={buttonVariants({ className: "hidden sm:inline-flex" })}
            to="/analysis"
          >
            New analysis
          </Link>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={Server}
          label="API status"
          value={health?.status ?? healthError ?? "Checking"}
          detail={health?.service ?? "http://127.0.0.1:8000"}
        />
        <MetricCard
          icon={Activity}
          label="Analyses"
          value="3"
          detail="Last 7 days"
        />
        <MetricCard
          icon={CheckCircle2}
          label="Completed reports"
          value="2"
          detail="Ready for review"
        />
        <MetricCard icon={Clock3} label="Drafts" value="1" detail="In progress" />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Latest report runs in the local workspace.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-border">
              {[
                ["AAPL", "Completed report", "2 hours ago"],
                ["NVDA", "Draft generated", "Yesterday"],
                ["MSFT", "Completed report", "Jun 18"],
              ].map(([symbol, event, time]) => (
                <div className="flex items-center justify-between gap-4 py-3" key={symbol}>
                  <div className="min-w-0">
                    <p className="font-medium">{symbol}</p>
                    <p className="text-sm text-muted-foreground">{event}</p>
                  </div>
                  <span className="shrink-0 text-sm text-muted-foreground">{time}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Provider readiness</CardTitle>
            <CardDescription>Current analysis provider configuration.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-md border border-border bg-muted p-4">
              <p className="text-sm font-medium">OpenAI</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Configure API credentials before running live analysis.
              </p>
            </div>
            <Link
              className={buttonVariants({
                className: "w-full",
                variant: "secondary",
              })}
              to="/settings"
            >
              Open settings
            </Link>
          </CardContent>
        </Card>
      </section>
    </>
  );
}

type MetricCardProps = {
  icon: LucideIcon;
  label: string;
  value: string;
  detail: string;
};

function MetricCard({ icon: Icon, label, value, detail }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted text-primary">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="truncate text-xl font-semibold">{value}</p>
          <p className="truncate text-xs text-muted-foreground">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}
