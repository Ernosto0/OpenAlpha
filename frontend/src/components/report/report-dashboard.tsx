import type { ReportDetail } from "../../lib/api";
import { TradingChart } from "../shared/trading-chart";
import { extractTradingHistory } from "../shared/trading-chart-data";
import { AgentTimeline } from "./agent-timeline";
import { CostBreakdownCard } from "./cost-breakdown-card";
import { EvidenceSignals } from "./evidence-signals";
import { PriceChartPlaceholder } from "./price-chart-placeholder";
import { ReportHeader } from "./report-header";
import { ReportMetricCards } from "./report-metric-cards";
import { ReportSidebar } from "./report-sidebar";
import { ScenarioCards } from "./scenario-cards";
import { WatchTriggerCards } from "./watch-trigger-cards";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

export function ReportDashboard({ report }: { report: ReportDetail }) {
  const finalReport = report.final_report as Record<string, unknown> | null;
  const tradingHistory = extractTradingHistory(report);

  return (
    <div className="space-y-8 mt-6">
      <ReportHeader report={report} />
      
      <ReportMetricCards report={report} />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px] items-start">
        {/* Left Column - Main Content */}
        <div className="space-y-8">
          <ScenarioCards report={report} />
          
          {tradingHistory.length > 0 ? (
            <Card className="bg-card shadow-panel">
              <CardHeader className="border-b border-border pb-4 flex flex-row items-center justify-between">
                <CardTitle className="text-sm">Price Action</CardTitle>
                {(finalReport as any)?.latest_close != null && (
                  <span className="text-sm font-mono text-muted-foreground">
                    Latest Close: <span className="text-foreground">${(finalReport as any).latest_close.toFixed(2)}</span>
                  </span>
                )}
              </CardHeader>
              <CardContent className="pt-6">
                <TradingChart bars={tradingHistory} />
              </CardContent>
            </Card>
          ) : (
            <PriceChartPlaceholder report={report} />
          )}

          <div className="grid gap-8 md:grid-cols-2">
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">Executive Summary</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {getString(finalReport?.executive_summary)}
              </p>
            </div>
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">Investment Thesis</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {getString(finalReport?.investment_thesis)}
              </p>
            </div>
          </div>

          <EvidenceSignals report={report} />

          <WatchTriggerCards report={report} />

          {getString(finalReport?.report_markdown) ? (
            <div className="space-y-4 pt-4 border-t border-border">
              <h3 className="text-sm font-semibold">Original Markdown Report</h3>
              <div className="rounded-lg border border-border bg-muted/20 p-6 overflow-x-auto">
                <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-foreground">
                  {getString(finalReport?.report_markdown)}
                </pre>
              </div>
            </div>
          ) : null}

          <div className="pt-4 border-t border-border space-y-8">
            <AgentTimeline report={report} />
            <CostBreakdownCard report={report} />
          </div>
        </div>

        {/* Right Column - Sidebar */}
        <ReportSidebar report={report} />
      </div>
    </div>
  );
}

function getString(value: unknown) {
  return typeof value === "string" ? value : null;
}
