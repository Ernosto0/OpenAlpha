import { cn } from "../../lib/utils";

export function DataQualityBar({ score }: { score: number }) {
  // score is 0-100
  const width = Math.min(Math.max(score, 0), 100);
  
  const getColorClass = (val: number) => {
    if (val >= 80) return "bg-success";
    if (val >= 50) return "bg-warning";
    return "bg-destructive";
  };

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div 
          className={cn("h-full transition-all duration-500", getColorClass(width))} 
          style={{ width: `${width}%` }} 
        />
      </div>
      <span className="text-xs font-mono font-medium tabular-nums">{width}/100</span>
    </div>
  );
}
