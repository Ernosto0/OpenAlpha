import { Activity, AlertTriangle, CheckCircle2, DollarSign, ShieldAlert } from "lucide-react";
import { formatOverallView, toRiskBadgeLevel } from "../../lib/analysis";
import type { ReportDetail } from "../../lib/api";
import { cn } from "../../lib/utils";

export function ReportMetricCards({ report }: { report: ReportDetail }) {
  const isBearish = report.overall_view.includes("bear");
  const riskLevel = toRiskBadgeLevel(report.risk_level);
  
  const dqScore = report.data_quality?.data_quality_score != null 
    ? Math.round(report.data_quality.data_quality_score * 100) 
    : null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      <MetricCard
        label="AI View"
        value={formatOverallView(report.overall_view)}
        icon={<Activity className="h-4 w-4" />}
        valueClass={isBearish ? "text-warning" : "text-success"}
      />
      <MetricCard
        label="Confidence"
        value={report.confidence != null ? `${Math.round(report.confidence * 100)}%` : "N/A"}
        icon={<CheckCircle2 className="h-4 w-4" />}
      />
      <MetricCard
        label="Risk Level"
        value={riskLevel}
        icon={<ShieldAlert className="h-4 w-4" />}
        valueClass={riskLevel === "High" ? "text-destructive" : riskLevel === "Medium" ? "text-warning" : "text-success"}
      />
      <MetricCard
        label="Data Quality"
        value={dqScore != null ? `${dqScore}/100` : "Unknown"}
        icon={<AlertTriangle className="h-4 w-4" />}
        valueClass={dqScore != null ? (dqScore >= 80 ? "text-success" : dqScore >= 50 ? "text-warning" : "text-destructive") : ""}
      />
      <MetricCard
        label="Est. Cost"
        value={`$${report.cost_breakdown.total_cost_usd.toFixed(4)}`}
        icon={<DollarSign className="h-4 w-4" />}
      />
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
  valueClass,
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
  valueClass?: string;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3 shadow-sm">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
      </div>
      <div className={cn("text-lg font-semibold", valueClass)}>
        {value}
      </div>
    </div>
  );
}
