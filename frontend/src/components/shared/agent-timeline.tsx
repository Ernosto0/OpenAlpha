import { CheckCircle2, CircleDashed, Loader2, AlertTriangle, XCircle } from "lucide-react";

export type AgentStatus = "pending" | "running" | "completed" | "partial" | "failed";

export type AgentRun = {
  id: string;
  name: string;
  status: AgentStatus;
  provider?: string;
  model?: string;
  cost?: string;
  duration?: string;
};

export function AgentTimeline({ agents }: { agents: AgentRun[] }) {
  const getIcon = (status: AgentStatus) => {
    switch (status) {
      case "pending":
        return <CircleDashed className="h-4 w-4 text-muted-foreground" />;
      case "running":
        return <Loader2 className="h-4 w-4 text-info animate-spin" />;
      case "completed":
        return <CheckCircle2 className="h-4 w-4 text-success" />;
      case "partial":
        return <AlertTriangle className="h-4 w-4 text-warning" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-destructive" />;
    }
  };

  return (
    <div className="space-y-4">
      {agents.map((agent, i) => (
        <div key={agent.id} className="relative flex gap-4">
          {i !== agents.length - 1 && (
            <div className="absolute left-[7px] top-6 bottom-[-16px] w-[2px] bg-border" />
          )}
          <div className="relative z-10 flex h-4 w-4 shrink-0 items-center justify-center bg-card mt-1">
            {getIcon(agent.status)}
          </div>
          <div className="flex-1 min-w-0 rounded-lg border border-border bg-card p-3 shadow-panel">
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm font-medium">{agent.name}</p>
              {agent.duration && (
                <span className="text-xs text-muted-foreground font-mono">{agent.duration}</span>
              )}
            </div>

            <div className="mt-2 text-xs font-mono uppercase tracking-wide text-muted-foreground">
              {agent.status}
            </div>
            
            {(agent.provider || agent.cost) && (
              <div className="mt-2 flex items-center gap-3 text-xs font-mono text-muted-foreground">
                {agent.provider && <span>{agent.provider}/{agent.model}</span>}
                {agent.cost && <span>CST: {agent.cost}</span>}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
