import { Calendar, Target } from "lucide-react";
import { formatOverallView, toRiskBadgeLevel } from "../../lib/analysis";
import type { ReportDetail } from "../../lib/api";
import { RiskBadge, StatusBadge } from "../shared/status-badges";

export function ReportHeader({ report }: { report: ReportDetail }) {
  const finalReport = report.final_report as Record<string, unknown> | null;
  const companyName = typeof finalReport?.company_name === "string" ? finalReport.company_name : "";

  return (
    <div className="flex flex-col gap-4 border-b border-border pb-6 pt-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <span className="text-primary">{report.symbol}</span>
          {companyName && (
            <>
              <span className="text-muted-foreground font-normal">·</span>
              <span>{companyName}</span>
            </>
          )}
        </h1>
        <p className="text-sm text-muted-foreground flex items-center gap-4 mt-2">
          <span className="flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5" />
            {new Date(report.created_at).toLocaleDateString()}
          </span>
          <span className="flex items-center gap-1.5">
            <Target className="h-3.5 w-3.5" />
            {report.horizon} Horizon
          </span>
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 mt-2">
        <StatusBadge
          status={formatOverallView(report.overall_view)}
          variant={report.overall_view.includes("bear") ? "warning" : "success"}
        />
        {report.confidence != null && (
          <div className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold font-mono bg-muted/20 text-foreground transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2">
            Conf: {Math.round(report.confidence * 100)}%
          </div>
        )}
        <RiskBadge level={toRiskBadgeLevel(report.risk_level)} />
      </div>
    </div>
  );
}
