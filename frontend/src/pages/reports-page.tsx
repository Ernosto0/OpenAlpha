import { Search, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { Input } from "../components/ui/input";
import { reportHistory } from "../data/reports";
import { StatusBadge, RiskBadge } from "../components/shared/status-badges";
import { DataQualityBar } from "../components/shared/data-quality-bar";

export function ReportsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Reports"
        title="Audit Logs & Reports"
        description="Review generated research reports, agent histories, and performance evaluations."
      />

      <div className="flex max-w-md items-center gap-2 mb-2">
        <div className="relative w-full">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input className="pl-9 bg-card border-border shadow-none" placeholder="Search by symbol or keyword..." type="search" />
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden shadow-panel">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-muted/50 text-muted-foreground font-mono text-xs uppercase tracking-wider border-b border-border">
              <tr>
                <th className="px-4 py-3 font-medium">Symbol</th>
                <th className="px-4 py-3 font-medium">AI View</th>
                <th className="px-4 py-3 font-medium text-right">Conf.</th>
                <th className="px-4 py-3 font-medium">Risk</th>
                <th className="px-4 py-3 font-medium">Horizon</th>
                <th className="px-4 py-3 font-medium w-32">Data Quality</th>
                <th className="px-4 py-3 font-medium">Model</th>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {reportHistory.map((report, i) => {
                // Mocking additional data for the table layout
                const mockView = i === 1 ? "Neutral" : "Bullish";
                const mockConf = i === 1 ? 65 : 85;
                const mockRisk = i === 1 ? "High" : "Medium";
                const mockScore = i === 1 ? 60 : 88;

                return (
                  <tr key={report.id} className="hover:bg-muted/30 transition-colors group">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-bold">{report.symbol}</span>
                        {report.status === "draft" && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-muted text-muted-foreground font-mono uppercase tracking-wider">Draft</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={mockView} variant={mockView === "Bullish" ? "success" : "warning"} className="px-2" />
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-mono font-medium">{mockConf}%</td>
                    <td className="px-4 py-3"><RiskBadge level={mockRisk as "Low" | "Medium" | "High"} /></td>
                    <td className="px-4 py-3 text-muted-foreground">6-12 Mo</td>
                    <td className="px-4 py-3">
                      <DataQualityBar score={mockScore} />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">gpt-4o</td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums text-xs">
                      {new Date(report.createdAt).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors hover:text-primary text-muted-foreground"
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
      </div>
    </>
  );
}
