export type CostItem = {
  label: string;
  model: string;
  costType?: string;
  durationMs?: number;
  warnings?: string[];
  parsingErrors?: string[];
  inputTokens: number;
  outputTokens: number;
  cost: number;
};

export function CostBreakdown({ items }: { items: CostItem[] }) {
  const totalCost = items.reduce((acc, item) => acc + item.cost, 0);

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left font-mono">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">Task</th>
              <th className="px-4 py-3 font-medium">Model</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium text-right">In</th>
              <th className="px-4 py-3 font-medium text-right">Out</th>
              <th className="px-4 py-3 font-medium text-right">Time</th>
              <th className="px-4 py-3 font-medium text-right">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((item, i) => (
              <tr key={i} className="hover:bg-muted/20 transition-colors">
                <td className="px-4 py-3 font-sans text-foreground">{item.label}</td>
                <td className="px-4 py-3 text-muted-foreground">{item.model}</td>
                <td className="px-4 py-3 text-muted-foreground">{item.costType ?? "api"}</td>
                <td className="px-4 py-3 text-right tabular-nums">{item.inputTokens.toLocaleString()}</td>
                <td className="px-4 py-3 text-right tabular-nums">{item.outputTokens.toLocaleString()}</td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {item.durationMs != null ? `${item.durationMs}ms` : "-"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-foreground">
                  ${item.cost.toFixed(4)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-muted/50 border-t border-border font-medium">
            <tr>
              <td colSpan={6} className="px-4 py-3 text-right">Total Estimated Cost</td>
              <td className="px-4 py-3 text-right text-foreground tabular-nums">${totalCost.toFixed(4)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
