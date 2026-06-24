import { formatAgentName } from "../../lib/analysis";
import type { ReportDetail } from "../../lib/api";
import { CostBreakdown } from "../shared/cost-breakdown";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

export function CostBreakdownCard({ report }: { report: ReportDetail }) {
  if (!report.cost_breakdown?.items || report.cost_breakdown.items.length === 0) {
    return null;
  }

  return (
    <Card className="bg-card shadow-panel">
      <CardHeader className="border-b border-border pb-4">
        <CardTitle className="text-sm">Cost Breakdown</CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        <CostBreakdown
          items={report.cost_breakdown.items.map((item) => ({
            label: formatAgentName(item.agent_name),
            model: `${item.provider}/${item.model}`,
            inputTokens: item.input_tokens,
            outputTokens: item.output_tokens,
            cost: item.cost_usd,
          }))}
        />
      </CardContent>
    </Card>
  );
}
