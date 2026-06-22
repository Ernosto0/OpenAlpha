import {
  Activity,
  CheckCircle2,
  Clock3,
  Server,
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
import { MetricCard } from "../components/shared/metric-card";
import { StatusBadge, RiskBadge } from "../components/shared/status-badges";
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
        title="Research Workstation"
        description="Local-first equity research environment. Track agents, data quality, and cost."
        actions={
          <Link
            className={buttonVariants({ variant: "primary", className: "hidden sm:inline-flex bg-primary text-primary-foreground font-semibold font-mono" })}
            to="/analysis"
          >
            + Run New Analysis
          </Link>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={Server}
          label="API Status"
          value={health?.status ?? healthError ?? "Checking"}
          detail={health?.service ?? "http://127.0.0.1:8000"}
        />
        <MetricCard
          icon={Activity}
          label="Active Agents"
          value="0"
          detail="Idle workspace"
        />
        <MetricCard
          icon={CheckCircle2}
          label="Completed Reports"
          value="32"
          detail="Locally stored"
        />
        <MetricCard icon={Clock3} label="Est. Cost Today" value="$0.12" detail="Using gpt-4o" />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card className="bg-card shadow-panel">
          <CardHeader className="pb-3 border-b border-border">
            <CardTitle className="text-lg">Recent Reports</CardTitle>
            <CardDescription>Latest completed analysis runs.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-border">
              {[
                { symbol: "AAPL", view: "Bullish", risk: "Low", date: "2 hours ago" },
                { symbol: "NVDA", view: "Neutral", risk: "High", date: "Yesterday" },
                { symbol: "MSFT", view: "Bullish", risk: "Medium", date: "Jun 18" },
              ].map((report) => (
                <div className="flex items-center justify-between p-4 hover:bg-muted/30 transition-colors" key={report.symbol}>
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 shrink-0 flex items-center justify-center rounded-md bg-muted font-bold tracking-tight">
                      {report.symbol}
                    </div>
                    <div>
                      <p className="font-semibold">{report.symbol} Analysis</p>
                      <p className="text-sm text-muted-foreground">{report.date}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={report.view} variant={report.view === "Bullish" ? "success" : "warning"} />
                    <RiskBadge level={report.risk as "Low" | "Medium" | "High"} />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="bg-card shadow-panel">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">System Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 font-mono text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Local DB</span>
                <span className="text-success">Connected</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">OpenAI Key</span>
                <span className="text-success">Valid</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Anthropic Key</span>
                <span className="text-muted-foreground">Missing</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Market Data</span>
                <span className="text-success">Active</span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card shadow-panel">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Performance Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium">Direction Correctness</span>
                  <span className="font-mono">78%</span>
                </div>
                <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-success w-[78%]" />
                </div>
              </div>
              <Link
                className={buttonVariants({
                  className: "w-full mt-4 bg-muted text-foreground hover:bg-muted/80 border border-border shadow-none",
                })}
                to="/performance"
              >
                View Full Tracking
              </Link>
            </CardContent>
          </Card>
        </div>
      </section>
    </>
  );
}
