import { type LucideIcon } from "lucide-react";

import { Card, CardContent } from "../ui/card";

export type MetricCardProps = {
  icon?: LucideIcon;
  label: string;
  value: string | number;
  detail?: string;
};

export function MetricCard({ icon: Icon, label, value, detail }: MetricCardProps) {
  return (
    <Card className="bg-card">
      <CardContent className="flex items-center gap-4 p-5">
        {Icon && (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-muted text-primary">
            <Icon className="h-5 w-5" aria-hidden="true" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="truncate text-2xl font-bold font-mono tabular-nums tracking-tight">
            {value}
          </p>
          {detail && <p className="truncate text-xs text-muted-foreground mt-1">{detail}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
