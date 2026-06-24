import type { ReportDetail } from "../../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { DataQualityCard } from "./data-quality-card";

export function ReportSidebar({ report }: { report: ReportDetail }) {
  return (
    <div className="space-y-6 sticky top-6">
      <DataQualityCard report={report} />

      <Card className="bg-card shadow-panel">
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-sm">Sources</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-4">
          {report.sources?.length ? (
            <div className="grid gap-2">
              {report.sources.map((source, i) => (
                <div
                  key={`${source.provider}-${source.name}-${i}`}
                  className="rounded-lg border border-border bg-muted/20 p-3"
                >
                  <p className="font-medium text-sm">{source.name}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {source.provider} · {source.used_for}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No sources recorded.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
