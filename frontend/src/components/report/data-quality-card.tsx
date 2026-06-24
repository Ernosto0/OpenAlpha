import { AlertCircle, CheckCircle2, HelpCircle } from "lucide-react";
import type { ReportDetail, ReportDataQuality } from "../../lib/api";
import { DataQualityBar } from "../shared/data-quality-bar";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { cn } from "../../lib/utils";

export function DataQualityCard({ report }: { report: ReportDetail }) {
  const dq = report.data_quality;

  if (!dq) {
    return (
      <Card className="bg-card shadow-panel">
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-sm">Data Quality</CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <p className="text-sm text-muted-foreground">Data quality metadata unavailable.</p>
        </CardContent>
      </Card>
    );
  }

  const score = dq.data_quality_score != null ? Math.round(dq.data_quality_score * 100) : 0;
  
  const hasIssues = dq.missing_data?.length > 0 || dq.warnings?.length > 0 || 
                    dq.price_data_status === "missing" || dq.news_data_status === "missing" ||
                    dq.price_data_status === "partial" || dq.news_data_status === "partial";

  return (
    <Card className="bg-card shadow-panel">
      <CardHeader className="border-b border-border pb-4">
        <CardTitle className="text-sm">Data Quality</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <DataQualityBar score={score} />
        
        <div className="space-y-2">
          <StatusRow label="Price Data" status={dq.price_data_status} />
          <StatusRow label="News Data" status={dq.news_data_status} />
          <StatusRow label="Profile Data" status={dq.company_profile_status} />
        </div>

        {hasIssues && (
          <div className="rounded-md bg-warning/10 p-3 border border-warning/20">
            <div className="flex items-start gap-2 text-warning">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <div className="space-y-1">
                <p className="text-xs font-medium">Partial or missing data detected.</p>
                {dq.missing_data?.length > 0 && (
                  <p className="text-xs opacity-80">Missing: {dq.missing_data.join(", ")}</p>
                )}
                {dq.warnings?.length > 0 && (
                  <p className="text-xs opacity-80">{dq.warnings[0]}</p>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StatusRow({ label, status }: { label: string; status: string }) {
  const isAvailable = status === "available" || status === "ok";
  const isPartial = status === "partial";
  
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-1.5">
        {isAvailable ? (
          <CheckCircle2 className="h-3.5 w-3.5 text-success" />
        ) : isPartial ? (
          <AlertCircle className="h-3.5 w-3.5 text-warning" />
        ) : (
          <HelpCircle className="h-3.5 w-3.5 text-destructive" />
        )}
        <span className={cn(
          "text-xs font-medium capitalize",
          isAvailable ? "text-success" : isPartial ? "text-warning" : "text-destructive"
        )}>
          {status || "unknown"}
        </span>
      </div>
    </div>
  );
}
