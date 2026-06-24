import { Newspaper, LineChart, ShieldAlert, FileText } from "lucide-react";
import type { ReportDetail } from "../../lib/api";
import { Card, CardContent } from "../ui/card";

export function EvidenceSignals({ report }: { report: ReportDetail }) {
  const finalReport = report.final_report as any;
  if (!finalReport) return null;

  const agentSummaries = finalReport.agent_summaries || {};
  const risks = finalReport.risk_section?.main_risks || [];
  
  const signals = [
    {
      id: "technical",
      title: "Technical Setup",
      content: agentSummaries.technical,
      icon: <LineChart className="h-4 w-4 text-info" />,
    },
    {
      id: "fundamental",
      title: "Fundamental Health",
      content: agentSummaries.fundamental,
      icon: <FileText className="h-4 w-4 text-success" />,
    },
    {
      id: "news",
      title: "News & Sentiment",
      content: agentSummaries.news_sentiment,
      icon: <Newspaper className="h-4 w-4 text-primary" />,
    },
    {
      id: "risk",
      title: "Primary Risks",
      content: risks.length > 0 ? risks.join(" • ") : null,
      icon: <ShieldAlert className="h-4 w-4 text-destructive" />,
    }
  ].filter(s => typeof s.content === "string" && s.content.trim().length > 0);

  if (signals.length === 0) return null;

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">Evidence & Signals</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {signals.map((signal) => (
          <Card key={signal.id} className="bg-card shadow-sm border-border/50">
            <CardContent className="p-4 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                {signal.icon}
                {signal.title}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {signal.content}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
