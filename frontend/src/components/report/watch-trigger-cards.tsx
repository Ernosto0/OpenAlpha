import { Bell } from "lucide-react";
import type { ReportDetail } from "../../lib/api";
import { Card, CardContent } from "../ui/card";

export function WatchTriggerCards({ report }: { report: ReportDetail }) {
  const finalReport = report.final_report as Record<string, unknown> | null;
  if (!finalReport) return null;

  const whatToWatch = Array.isArray(finalReport.what_to_watch) 
    ? finalReport.what_to_watch.filter(item => typeof item === "string" && item.trim().length > 0) 
    : [];

  if (whatToWatch.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold flex items-center gap-2">
        <Bell className="h-4 w-4" />
        What To Watch
      </h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {whatToWatch.map((trigger, idx) => (
          <Card key={idx} className="bg-muted/10 border-border/60 shadow-none">
            <CardContent className="p-4 flex gap-3">
              <div className="mt-0.5 w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
              <p className="text-sm text-muted-foreground leading-relaxed">
                {trigger}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
