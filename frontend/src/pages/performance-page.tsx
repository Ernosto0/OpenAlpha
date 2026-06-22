import { BarChart, History, Target, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { MetricCard } from "../components/shared/metric-card";
import { StatusBadge } from "../components/shared/status-badges";
import { Badge } from "../components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { formatOverallView } from "../lib/analysis";
import {
  api,
  type PerformanceBreakdownItem,
  type PerformanceEvaluationItem,
  type PerformanceResponse,
} from "../lib/api";

export function PerformancePage() {
  const [performance, setPerformance] = useState<PerformanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    api
      .getPerformance()
      .then((data) => {
        if (!active) {
          return;
        }

        setPerformance(data);
        setError(null);
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setError("Unable to load performance data.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const hasData = (performance?.summary.total_reports ?? 0) > 0;

  return (
    <>
      <PageHeader
        eyebrow="Performance"
        title="Model & Portfolio Tracking"
        description="Evaluate the accuracy of AI research against market reality."
      />

      <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={Target}
          label="Direction Correctness"
          value={loading ? "Loading" : formatPercent(performance?.summary.direction_correctness)}
          detail="Scored directional views"
        />
        <MetricCard
          icon={TrendingUp}
          label="Relative Performance"
          value={loading ? "Loading" : formatPercent(performance?.summary.relative_performance, true)}
          detail="Average alpha vs benchmark"
        />
        <MetricCard
          icon={BarChart}
          label="Evaluated Reports"
          value={
            loading
              ? "Loading"
              : `${performance?.summary.evaluated_reports ?? 0}/${performance?.summary.total_reports ?? 0}`
          }
          detail="Reports with usable price history"
        />
        <MetricCard
          icon={History}
          label="Avg Hold Time"
          value={loading ? "Loading" : formatDays(performance?.summary.average_hold_days)}
          detail="Elapsed days since report creation"
        />
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <BreakdownCard
          description="Accuracy rate of directional calls by resolved model."
          items={performance?.by_model ?? []}
          loading={loading}
          title="Performance by Model"
        />
        <BreakdownCard
          description="Accuracy and returns across report horizons."
          items={performance?.by_horizon ?? []}
          loading={loading}
          title="Performance by Horizon"
        />
      </div>

      <Card className="bg-card shadow-panel">
        <CardHeader className="border-b border-border pb-3">
          <CardTitle>Recent Evaluated Reports</CardTitle>
          <CardDescription>
            Interim rows are mark-to-market; matured rows have fully elapsed their target horizon.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-4 text-sm text-muted-foreground">Loading performance data...</div>
          ) : error ? (
            <div className="p-4 text-sm text-destructive">{error}</div>
          ) : !hasData ? (
            <div className="p-4 text-sm text-muted-foreground">
              No reports are available for performance evaluation yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-muted/50 font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Symbol</th>
                    <th className="px-4 py-3 font-medium">Model</th>
                    <th className="px-4 py-3 font-medium">AI View</th>
                    <th className="px-4 py-3 font-medium">Return</th>
                    <th className="px-4 py-3 font-medium">Alpha</th>
                    <th className="px-4 py-3 font-medium">Horizon</th>
                    <th className="px-4 py-3 font-medium">Window</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {performance?.recent_evaluations.map((item) => (
                    <EvaluationRow item={item} key={item.report_id} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function BreakdownCard({
  title,
  description,
  items,
  loading,
}: {
  title: string;
  description: string;
  items: PerformanceBreakdownItem[];
  loading: boolean;
}) {
  return (
    <Card className="bg-card shadow-panel">
      <CardHeader className="border-b border-border pb-3">
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="pt-6">
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading breakdown...</div>
        ) : items.length === 0 ? (
          <div className="text-sm text-muted-foreground">No performance data available.</div>
        ) : (
          <div className="space-y-6">
            {items.map((item) => {
              const correctness = item.correctness_rate ?? 0;
              const percent = Math.max(0, Math.min(correctness * 100, 100));
              const toneClass =
                percent >= 70 ? "bg-success text-success" : percent >= 50 ? "bg-warning text-warning" : "bg-destructive text-destructive";

              return (
                <div key={item.label}>
                  <div className="mb-2 flex items-center justify-between gap-3 text-sm font-mono">
                    <span className="truncate">{item.label}</span>
                    <span className={percent >= 70 ? "text-success" : percent >= 50 ? "text-warning" : "text-destructive"}>
                      {formatPercent(item.correctness_rate)}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div className={`h-full ${toneClass.split(" ")[0]}`} style={{ width: `${percent}%` }} />
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                    <span>{item.evaluated_count} evaluated</span>
                    <span>
                      Avg return {formatPercent(item.average_return, true)} / alpha{" "}
                      {formatPercent(item.average_alpha, true)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function EvaluationRow({ item }: { item: PerformanceEvaluationItem }) {
  const view = formatOverallView(item.overall_view);
  const viewVariant =
    item.overall_view.includes("bear") ? "warning" : item.overall_view === "neutral" ? "info" : "success";
  const directionVariant =
    item.direction_result === "correct"
      ? "success"
      : item.direction_result === "incorrect"
        ? "destructive"
        : "secondary";

  return (
    <tr className="transition-colors hover:bg-muted/30">
      <td className="px-4 py-3">
        <Link className="font-bold hover:text-primary" to={`/reports/${item.report_id}`}>
          {item.symbol}
        </Link>
      </td>
      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{item.model}</td>
      <td className="px-4 py-3">
        <StatusBadge className="px-2" status={view} variant={viewVariant} />
      </td>
      <td className={valueToneClass(item.realized_return, "px-4 py-3 font-mono tabular-nums")}>
        {formatPercent(item.realized_return, true)}
      </td>
      <td className={valueToneClass(item.alpha, "px-4 py-3 font-mono tabular-nums")}>
        {formatPercent(item.alpha, true)}
      </td>
      <td className="px-4 py-3 text-muted-foreground">{item.horizon}</td>
      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
        {item.days_elapsed}/{item.target_days}d
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={item.evaluation_status === "matured" ? "success" : "warning"}>
            {item.evaluation_status}
          </Badge>
          <StatusBadge
            status={directionLabel(item.direction_result)}
            variant={directionVariant}
          />
        </div>
      </td>
    </tr>
  );
}

function directionLabel(value: PerformanceEvaluationItem["direction_result"]) {
  if (value === "not_scored") {
    return "Not Scored";
  }
  return value === "correct" ? "Correct" : "Incorrect";
}

function formatPercent(value: number | null | undefined, signed = false) {
  if (value === null || value === undefined) {
    return "N/A";
  }

  const formatted = `${(value * 100).toFixed(1)}%`;
  if (!signed) {
    return formatted;
  }
  return value > 0 ? `+${formatted}` : formatted;
}

function formatDays(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return `${Math.round(value)}d`;
}

function valueToneClass(value: number | null | undefined, baseClassName: string) {
  if (value === null || value === undefined) {
    return `${baseClassName} text-muted-foreground`;
  }
  if (value > 0) {
    return `${baseClassName} text-success`;
  }
  if (value < 0) {
    return `${baseClassName} text-destructive`;
  }
  return `${baseClassName} text-muted-foreground`;
}
