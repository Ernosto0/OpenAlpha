import { Badge } from "./ui/badge";

type StatusBadgeProps = {
  status: "draft" | "complete" | "failed";
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const variant =
    status === "complete" ? "success" : status === "failed" ? "danger" : "warning";

  return <Badge variant={variant}>{status}</Badge>;
}
