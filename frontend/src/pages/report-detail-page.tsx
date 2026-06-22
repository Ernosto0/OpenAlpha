import { ArrowLeft, CheckCircle2, ShieldAlert } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { buttonVariants } from "../components/ui/button-styles";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { StatusBadge, RiskBadge } from "../components/shared/status-badges";
import { DataQualityBar } from "../components/shared/data-quality-bar";
import { CostBreakdown } from "../components/shared/cost-breakdown";
import { reportDetails } from "../data/reports";

export function ReportDetailPage() {
  const { id } = useParams();
  const report = id ? reportDetails[id] : undefined;

  if (!report) {
    return (
      <>
        <PageHeader title="Report not found" description="The requested report does not exist." />
        <Link className={buttonVariants({ variant: "secondary" })} to="/reports">
          Back to reports
        </Link>
      </>
    );
  }

  // Safe fallbacks for new Audit Terminal fields not yet in backend
  const aiView = "Bullish"; 
  const confidence = 85; 
  const riskLevel = "Medium"; 
  const horizon = "6-12 Months";
  const priceAtReport = "$145.32";
  
  const bullCase = report.thesis + " If execution accelerates, upside could be significant given current multiples.";
  const bearCase = "Conversely, if macroeconomic conditions worsen, revenue could contract and compress margins.";
  const invalidation = "Thesis invalidates if next quarter revenue growth drops below 5% or gross margins compress by >200bps.";
  const whatToWatch = "Upcoming earnings call, competitor product announcements, and changes in regulatory policy.";

  const mockCosts = [
    { label: "Data Collection", model: "gpt-4o-mini", inputTokens: 45000, outputTokens: 1200, cost: 0.0068 },
    { label: "Analysis Pass", model: "claude-3.5-sonnet", inputTokens: 32000, outputTokens: 4000, cost: 0.0960 + 0.0600 },
    { label: "Synthesis", model: "gpt-4o", inputTokens: 15000, outputTokens: 2500, cost: 0.0750 + 0.0375 },
  ];

  return (
    <>
      <div className="mb-6 flex items-center gap-4">
        <Link className={buttonVariants({ variant: "secondary", className: "h-8 px-3 font-mono text-xs bg-transparent hover:bg-muted text-muted-foreground" })} to="/reports">
          <ArrowLeft className="h-3 w-3 mr-2" aria-hidden="true" />
          BACK TO REPORTS
        </Link>
      </div>

      <header className="mb-8">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-bold tracking-tight">{report.symbol}</h1>
              <span className="text-xl text-muted-foreground font-light border-l border-border pl-3">Apple Inc.</span>
            </div>
            <p className="text-muted-foreground font-mono text-sm uppercase tracking-wider">Equity Research Report</p>
          </div>
          <div className="flex flex-wrap items-center gap-3 font-mono text-sm">
            <div className="flex items-center gap-2 bg-muted/50 px-3 py-1.5 rounded-md border border-border">
              <span className="text-muted-foreground">PRICE:</span>
              <span className="text-foreground">{priceAtReport}</span>
            </div>
            <div className="flex items-center gap-2 bg-muted/50 px-3 py-1.5 rounded-md border border-border">
              <span className="text-muted-foreground">DATE:</span>
              <span className="text-foreground">{new Date(report.createdAt).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Top Summary Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div className="bg-card border border-border rounded-lg p-4 flex flex-col justify-center">
          <span className="text-xs text-muted-foreground font-mono uppercase mb-1">AI View</span>
          <div><StatusBadge status={aiView} variant="success" className="text-sm px-2 py-1" /></div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4 flex flex-col justify-center">
          <span className="text-xs text-muted-foreground font-mono uppercase mb-1">Risk Level</span>
          <div><RiskBadge level={riskLevel as "Low" | "Medium" | "High"} /></div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4 flex flex-col justify-center">
          <span className="text-xs text-muted-foreground font-mono uppercase mb-1">Confidence</span>
          <div className="text-xl font-bold tabular-nums text-foreground">{confidence}%</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4 flex flex-col justify-center">
          <span className="text-xs text-muted-foreground font-mono uppercase mb-1">Time Horizon</span>
          <div className="font-medium text-foreground">{horizon}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4 flex flex-col justify-center">
          <span className="text-xs text-muted-foreground font-mono uppercase mb-1">Status</span>
          <div className="flex items-center gap-2 font-medium text-success">
            <CheckCircle2 className="h-4 w-4" />
            Complete
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Main Content Column */}
        <div className="space-y-6">
          <section className="space-y-3">
            <h2 className="text-lg font-semibold border-b border-border pb-2">Investment Thesis</h2>
            <p className="leading-relaxed text-foreground">{report.thesis}</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold border-b border-border pb-2 text-success">Bull Case</h2>
            <p className="leading-relaxed text-muted-foreground">{bullCase}</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold border-b border-border pb-2 text-destructive">Bear Case</h2>
            <p className="leading-relaxed text-muted-foreground">{bearCase}</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold border-b border-border pb-2 text-warning">Risk Review</h2>
            <ul className="list-disc pl-5 space-y-2 text-muted-foreground">
              {report.risks.map((risk, i) => (
                <li key={i}>{risk}</li>
              ))}
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold border-b border-border pb-2">Invalidation Conditions</h2>
            <p className="leading-relaxed text-muted-foreground">{invalidation}</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold border-b border-border pb-2">What to Watch</h2>
            <p className="leading-relaxed text-muted-foreground">{whatToWatch}</p>
          </section>
        </div>

        {/* Right Audit Panel */}
        <div className="space-y-6">
          <Card className="bg-card shadow-panel border-border">
            <CardHeader className="pb-3 bg-muted/20 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider flex items-center gap-2">
                <ShieldAlert className="h-4 w-4" />
                Audit Trail
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-6">
              
              <div className="space-y-2">
                <h3 className="text-xs font-mono text-muted-foreground uppercase">Data Quality</h3>
                <DataQualityBar score={88} />
                <p className="text-xs text-muted-foreground mt-1">Based on source diversity and freshness.</p>
              </div>

              <div className="space-y-2">
                <h3 className="text-xs font-mono text-muted-foreground uppercase">Sources Used ({report.sources.length})</h3>
                <div className="flex flex-col gap-1.5">
                  {report.sources.map((source) => (
                    <div key={source} className="flex items-center gap-2 text-sm bg-muted/30 px-2 py-1.5 rounded border border-border">
                      <div className="h-1.5 w-1.5 rounded-full bg-success shrink-0" />
                      <span className="truncate">{source}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <h3 className="text-xs font-mono text-muted-foreground uppercase">Warnings</h3>
                <div className="bg-warning/10 border border-warning/20 text-warning px-3 py-2 rounded-md text-xs leading-relaxed">
                  <strong>Notice:</strong> High variance in sentiment across news sources. Technical indicators conflict with fundamental momentum.
                </div>
              </div>

            </CardContent>
          </Card>

          <Card className="bg-card shadow-panel border-border">
            <CardHeader className="pb-3 bg-muted/20 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider">Run Telemetry</CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              <CostBreakdown items={mockCosts} />
            </CardContent>
          </Card>

          <div className="text-[10px] leading-relaxed text-muted-foreground/60 p-4 border border-border/50 rounded-lg bg-card/50">
            <strong>Disclaimer:</strong> This report is generated by an AI system for research and educational purposes only. It is not personalized financial advice, investment advice, or a recommendation to buy or sell any security. Data may be delayed, inaccurate, or hallucinated. Always do your own research.
          </div>
        </div>
      </div>
    </>
  );
}
