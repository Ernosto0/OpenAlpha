import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import type { ReportDetail } from "../../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { cn } from "../../lib/utils";

export function ScenarioCards({ report }: { report: ReportDetail }) {
  const finalReport = report.final_report as Record<string, unknown> | null;
  if (!finalReport) return null;

  const baseCase = typeof finalReport.base_case === "string" ? finalReport.base_case : null;
  const bullCase = typeof finalReport.bull_case_summary === "string" ? finalReport.bull_case_summary : null;
  const bearCase = typeof finalReport.bear_case_summary === "string" ? finalReport.bear_case_summary : null;

  if (!baseCase && !bullCase && !bearCase) return null;

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <ScenarioCard
        title="Bear Case"
        content={bearCase}
        icon={<TrendingDown className="h-5 w-5 text-destructive" />}
        borderColor="border-destructive/30"
        headerBg="bg-destructive/10"
      />
      <ScenarioCard
        title="Base Case"
        content={baseCase}
        icon={<Minus className="h-5 w-5 text-muted-foreground" />}
        borderColor="border-border"
        headerBg="bg-muted/20"
      />
      <ScenarioCard
        title="Bull Case"
        content={bullCase}
        icon={<TrendingUp className="h-5 w-5 text-success" />}
        borderColor="border-success/30"
        headerBg="bg-success/10"
      />
    </div>
  );
}

function ScenarioCard({
  title,
  content,
  icon,
  borderColor,
  headerBg,
}: {
  title: string;
  content: string | null;
  icon: React.ReactNode;
  borderColor: string;
  headerBg: string;
}) {
  if (!content) return null;

  return (
    <Card className={cn("bg-card shadow-panel overflow-hidden", borderColor)}>
      <CardHeader className={cn("p-4 border-b border-border/50", headerBg)}>
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 text-sm leading-relaxed text-muted-foreground">
        {content}
      </CardContent>
    </Card>
  );
}
