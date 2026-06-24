import { Clock, Cpu, Server, AlertCircle } from "lucide-react";
import { formatAgentName } from "../../lib/analysis";
import type { ReportDetail } from "../../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { cn } from "../../lib/utils";

export function AgentTimeline({ report }: { report: ReportDetail }) {
  const agents = report.agent_outputs || [];
  
  if (agents.length === 0) return null;

  return (
    <Card className="bg-card shadow-panel">
      <CardHeader className="border-b border-border pb-4">
        <CardTitle className="text-sm">Agent Audit Trail</CardTitle>
      </CardHeader>
      <CardContent className="pt-6 relative">
        <div className="absolute left-6 top-6 bottom-6 w-px bg-border/60 z-0 hidden sm:block" />
        <div className="space-y-6 relative z-10">
          {agents.map((agent, idx) => (
            <div key={`${agent.agent_name}-${idx}`} className="flex flex-col sm:flex-row gap-4">
              <div className="hidden sm:flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-muted/50 text-xs font-mono">
                {idx + 1}
              </div>
              <div className="flex-1 rounded-lg border border-border/60 bg-muted/5 p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="font-medium text-sm text-foreground">
                    {formatAgentName(agent.agent_name)}
                  </h4>
                  <div className="flex items-center gap-2 text-xs">
                    <span className={cn(
                      "px-2 py-0.5 rounded-full border",
                      agent.status === "completed" ? "border-success/30 text-success bg-success/10" : 
                      agent.status === "failed" ? "border-destructive/30 text-destructive bg-destructive/10" : 
                      "border-border text-muted-foreground"
                    )}>
                      {agent.status}
                    </span>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <Server className="h-3.5 w-3.5" />
                    <span>{agent.provider}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5" />
                    <span className="truncate" title={agent.model}>{agent.model}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" />
                    <span>{agent.duration_ms}ms</span>
                  </div>
                  <div className="flex items-center gap-1.5 font-mono">
                    <span>${agent.cost_usd.toFixed(4)}</span>
                  </div>
                </div>

                {agent.warnings && agent.warnings.length > 0 && (
                  <div className="mt-2 flex items-start gap-1.5 text-xs text-warning bg-warning/10 rounded px-2 py-1.5 border border-warning/20">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      {agent.warnings.map((w, i) => (
                        <p key={i}>{w}</p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
