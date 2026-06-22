import { ChevronRight, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { DataQualityBar } from "../components/shared/data-quality-bar";
import { RiskBadge, StatusBadge } from "../components/shared/status-badges";
import { PageHeader } from "../components/page-header";
import { Input } from "../components/ui/input";
import {
  formatOverallView,
  toRiskBadgeLevel,
} from "../lib/analysis";
import { api, type ReportSummary } from "../lib/api";

export function ReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    api
      .listReports()
      .then((data) => {
        if (!active) {
          return;
        }

        setReports(data);
        setError(null);
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setError("Unable to load reports.");
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

  const filteredReports = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return reports;
    }

    return reports.filter((report) =>
      [report.symbol, report.overall_view, report.horizon]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery),
    );
  }, [query, reports]);

  return (
    <>
      <PageHeader
        eyebrow="Reports"
        title="Audit Logs & Reports"
        description="Review generated research reports, agent histories, and performance evaluations."
      />

      <div className="mb-2 flex max-w-md items-center gap-2">
        <div className="relative w-full">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            className="border-border bg-card pl-9 shadow-none"
            placeholder="Search by symbol, horizon, or view..."
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-card shadow-panel">
        {loading ? (
          <div className="p-4 text-sm text-muted-foreground">Loading reports...</div>
        ) : error ? (
          <div className="p-4 text-sm text-destructive">{error}</div>
        ) : filteredReports.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground">
            No reports matched the current search.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/50 font-mono text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Symbol</th>
                  <th className="px-4 py-3 font-medium">AI View</th>
                  <th className="px-4 py-3 font-medium text-right">Conf.</th>
                  <th className="px-4 py-3 font-medium">Risk</th>
                  <th className="px-4 py-3 font-medium">Horizon</th>
                  <th className="px-4 py-3 font-medium w-32">Data Quality</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredReports.map((report) => {
                  const score = Math.round((report.confidence ?? 0) * 100);
                  const view = formatOverallView(report.overall_view);

                  return (
                    <tr
                      key={report.id}
                      className="group transition-colors hover:bg-muted/30"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-bold">{report.symbol}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          status={view}
                          variant={view === "Bullish" ? "success" : "warning"}
                          className="px-2"
                        />
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-medium tabular-nums">
                        {score}%
                      </td>
                      <td className="px-4 py-3">
                        <RiskBadge level={toRiskBadgeLevel(report.risk_level)} />
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {report.horizon}
                      </td>
                      <td className="px-4 py-3">
                        <DataQualityBar score={score} />
                      </td>
                      <td className="px-4 py-3 text-xs tabular-nums text-muted-foreground">
                        {new Date(report.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          className="inline-flex items-center justify-center rounded-md text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
                          to={`/reports/${report.id}`}
                        >
                          <span className="sr-only">Open report</span>
                          <ChevronRight className="h-5 w-5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
