import { ArrowLeft } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { CostBreakdown } from "../components/shared/cost-breakdown";
import { DataQualityBar } from "../components/shared/data-quality-bar";
import { RiskBadge, StatusBadge } from "../components/shared/status-badges";
import { buttonVariants } from "../components/ui/button-styles";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import {
  formatAgentName,
  formatOverallView,
  toRiskBadgeLevel,
} from "../lib/analysis";
import { api, type ReportDetail } from "../lib/api";

export function ReportDetailPage() {
  const { id } = useParams();
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      setError("Report not found.");
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    api
      .getReport(id)
      .then((detail) => {
        if (!active) {
          return;
        }

        setReport(detail);
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setError("Unable to load report.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [id]);

  const finalReport = useMemo(() => {
    if (!report?.final_report || typeof report.final_report !== "object") {
      return null;
    }

    return report.final_report as Record<string, unknown>;
  }, [report]);

  return (
    <>
      <div className="mb-6">
        <Link
          className={buttonVariants({
            variant: "secondary",
            className: "font-mono text-xs",
          })}
          to="/reports"
        >
          <ArrowLeft className="mr-2 h-3 w-3" aria-hidden="true" />
          Back To Reports
        </Link>
      </div>

      <PageHeader
        eyebrow="Report"
        title={report ? `${report.symbol} Research Report` : "Report Detail"}
        description="Persisted final report, cost trace, and data quality summary."
      />

      {loading ? (
        <Card className="bg-card shadow-panel">
          <CardContent className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            Loading report...
          </CardContent>
        </Card>
      ) : error || !report ? (
        <Card className="bg-card shadow-panel">
          <CardContent className="flex h-40 items-center justify-center text-sm text-destructive">
            {error ?? "Report not found."}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <MetricCard
              label="AI View"
              value={
                <StatusBadge
                  status={formatOverallView(report.overall_view)}
                  variant={report.overall_view.includes("bear") ? "warning" : "success"}
                />
              }
            />
            <MetricCard
              label="Risk"
              value={<RiskBadge level={toRiskBadgeLevel(report.risk_level)} />}
            />
            <MetricCard
              label="Horizon"
              value={<span className="font-mono">{report.horizon}</span>}
            />
            <MetricCard
              label="Cost"
              value={<span className="font-mono">${report.cost_breakdown.total_cost_usd.toFixed(4)}</span>}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <Card className="bg-card shadow-panel">
              <CardHeader className="border-b border-border pb-4">
                <CardTitle>Final Report</CardTitle>
                <CardDescription>
                  Inline view of the persisted report payload.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 pt-6">
                <Section
                  title="Executive Summary"
                  body={getString(finalReport?.executive_summary)}
                />
                <Section
                  title="Investment Thesis"
                  body={getString(finalReport?.investment_thesis)}
                />
                <Section
                  title="Base Case"
                  body={getString(finalReport?.base_case)}
                />
                <Section
                  title="Bull Case"
                  body={getString(finalReport?.bull_case_summary)}
                />
                <Section
                  title="Bear Case"
                  body={getString(finalReport?.bear_case_summary)}
                />

                {getString(finalReport?.report_markdown) ? (
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold">Rendered Report</h3>
                    <div className="rounded-lg border border-border bg-muted/20 p-4">
                      <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
                        {getString(finalReport?.report_markdown)}
                      </pre>
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card className="bg-card shadow-panel">
                <CardHeader className="border-b border-border pb-4">
                  <CardTitle>Data Quality</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 pt-6">
                  {report.data_quality?.data_quality_score != null ? (
                    <>
                      <DataQualityBar score={Math.round(report.data_quality.data_quality_score * 100)} />
                      <p className="text-sm text-muted-foreground">
                        Price: {report.data_quality.price_data_status} · News: {report.data_quality.news_data_status}
                      </p>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Data quality metadata unavailable.
                    </p>
                  )}
                </CardContent>
              </Card>

              <Card className="bg-card shadow-panel">
                <CardHeader className="border-b border-border pb-4">
                  <CardTitle>Sources</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 pt-6">
                  {report.sources.length ? (
                    report.sources.map((source) => (
                      <div
                        key={`${source.provider}-${source.name}-${source.used_for}`}
                        className="rounded-lg border border-border bg-muted/20 p-3"
                      >
                        <p className="font-medium">{source.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {source.provider} · {source.used_for}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">No sources recorded.</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>

          <Card className="bg-card shadow-panel">
            <CardHeader className="border-b border-border pb-4">
              <CardTitle>Cost Breakdown</CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <CostBreakdown
                items={report.cost_breakdown.items.map((item) => ({
                  label: formatAgentName(item.agent_name),
                  model: `${item.provider}/${item.model}`,
                  inputTokens: item.input_tokens,
                  outputTokens: item.output_tokens,
                  cost: item.cost_usd,
                }))}
              />
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-panel">
      <p className="text-xs font-mono uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-2">{value}</div>
    </div>
  );
}

function Section({
  title,
  body,
}: {
  title: string;
  body: string | null;
}) {
  if (!body) {
    return null;
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="text-sm leading-6 text-foreground">{body}</p>
    </div>
  );
}

function getString(value: unknown) {
  return typeof value === "string" ? value : null;
}
