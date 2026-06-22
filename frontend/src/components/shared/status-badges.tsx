import { cn } from "../../lib/utils";

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  status: string;
  variant?: "default" | "secondary" | "destructive" | "success" | "warning" | "info";
}

export function StatusBadge({ className, variant = "default", status, ...props }: StatusBadgeProps) {
  const getVariantClass = () => {
    switch (variant) {
      case "default": return "bg-primary text-primary-foreground";
      case "secondary": return "bg-secondary text-secondary-foreground";
      case "destructive": return "bg-destructive text-destructive-foreground";
      case "success": return "bg-success text-primary-foreground";
      case "warning": return "bg-warning text-primary-foreground";
      case "info": return "bg-info text-primary-foreground";
      default: return "";
    }
  };

  return (
    <div 
      className={cn(
        "inline-flex items-center rounded-md border border-transparent px-2.5 py-0.5 text-xs font-mono font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        getVariantClass(),
        className
      )} 
      {...props}
    >
      {status}
    </div>
  );
}

export function RiskBadge({ level }: { level: "Low" | "Medium" | "High" }) {
  const variant = level === "High" ? "destructive" : level === "Medium" ? "warning" : "success";
  return <StatusBadge status={`${level} Risk`} variant={variant} />;
}

