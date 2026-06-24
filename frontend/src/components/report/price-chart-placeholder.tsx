import { BarChart3 } from "lucide-react";
import type { ReportDetail } from "../../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

export function PriceChartPlaceholder({ report }: { report: ReportDetail }) {
  const latestClose = (report.final_report as any)?.latest_close;
  
  return (
    <Card className="bg-card shadow-panel">
      <CardHeader className="border-b border-border pb-4 flex flex-row items-center justify-between">
        <CardTitle className="text-sm">Price Action</CardTitle>
        {latestClose != null && (
          <span className="text-sm font-mono text-muted-foreground">
            Latest Close: <span className="text-foreground">${latestClose.toFixed(2)}</span>
          </span>
        )}
      </CardHeader>
      <CardContent className="pt-6">
        <div className="h-64 w-full rounded-lg border border-dashed border-border/60 bg-muted/5 flex flex-col items-center justify-center text-muted-foreground gap-3">
          <BarChart3 className="h-8 w-8 opacity-50" />
          <div className="text-center">
            <p className="text-sm font-medium">Chart Unavailable</p>
            <p className="text-xs opacity-70 mt-1 max-w-xs px-4">
              A chart library like TradingView Lightweight Charts is required to render price history.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
