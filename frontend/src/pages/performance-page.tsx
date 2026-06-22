import { Target, TrendingUp, BarChart, History } from "lucide-react";
import { PageHeader } from "../components/page-header";
import { MetricCard } from "../components/shared/metric-card";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";

export function PerformancePage() {
  return (
    <>
      <PageHeader
        eyebrow="Performance"
        title="Model & Portfolio Tracking"
        description="Evaluate the accuracy of AI research against market reality."
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 mb-6">
        <MetricCard
          icon={Target}
          label="Direction Correctness"
          value="78.5%"
          detail="All models, TTM"
        />
        <MetricCard
          icon={TrendingUp}
          label="Relative Performance"
          value="+4.2%"
          detail="vs S&P 500"
        />
        <MetricCard
          icon={BarChart}
          label="Evaluated Reports"
          value="142"
          detail="Out of 180 total"
        />
        <MetricCard 
          icon={History} 
          label="Avg Hold Time" 
          value="8 Mo" 
          detail="For realized picks" 
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2 mb-6">
        <Card className="bg-card shadow-panel">
          <CardHeader className="border-b border-border pb-3">
            <CardTitle>Performance by Model</CardTitle>
            <CardDescription>Accuracy rate of directional calls.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="space-y-6">
              <div>
                <div className="flex justify-between text-sm mb-2 font-mono">
                  <span>gpt-4o</span>
                  <span className="text-success">81.2%</span>
                </div>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-success w-[81.2%]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2 font-mono">
                  <span>claude-3.5-sonnet</span>
                  <span className="text-success">79.5%</span>
                </div>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-success w-[79.5%]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2 font-mono">
                  <span>llama-3-70b</span>
                  <span className="text-warning">65.0%</span>
                </div>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-warning w-[65%]" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card shadow-panel">
          <CardHeader className="border-b border-border pb-3">
            <CardTitle>Performance by Horizon</CardTitle>
            <CardDescription>Accuracy breakdown across time horizons.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="space-y-6">
              <div>
                <div className="flex justify-between text-sm mb-2 font-mono">
                  <span>Short Term (1-3 Mo)</span>
                  <span className="text-warning">55.4%</span>
                </div>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-warning w-[55.4%]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2 font-mono">
                  <span>Medium Term (6-12 Mo)</span>
                  <span className="text-success">82.1%</span>
                </div>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-success w-[82.1%]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2 font-mono">
                  <span>Long Term (1-3 Yr)</span>
                  <span className="text-success">88.5%</span>
                </div>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-success w-[88.5%]" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-card shadow-panel">
        <CardHeader className="border-b border-border pb-3">
          <CardTitle>Recent Evaluated Reports</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-muted/50 text-muted-foreground font-mono text-xs uppercase tracking-wider border-b border-border">
                <tr>
                  <th className="px-4 py-3 font-medium">Symbol</th>
                  <th className="px-4 py-3 font-medium">AI View</th>
                  <th className="px-4 py-3 font-medium">Realized Return</th>
                  <th className="px-4 py-3 font-medium">Alpha (vs SPY)</th>
                  <th className="px-4 py-3 font-medium">Eval Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-bold">META</td>
                  <td className="px-4 py-3 text-success">Bullish</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-success">+34.2%</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-success">+18.5%</td>
                  <td className="px-4 py-3 font-mono text-xs text-success uppercase">Correct</td>
                </tr>
                <tr className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-bold">TSLA</td>
                  <td className="px-4 py-3 text-success">Bullish</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-destructive">-12.4%</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-destructive">-24.1%</td>
                  <td className="px-4 py-3 font-mono text-xs text-destructive uppercase">Incorrect</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
