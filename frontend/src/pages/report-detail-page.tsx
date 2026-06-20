import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { StatusBadge } from "../components/status-badge";
import { buttonVariants } from "../components/ui/button-styles";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
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

  return (
    <>
      <PageHeader
        eyebrow={report.symbol}
        title={report.title}
        description={`Created ${new Date(report.createdAt).toLocaleString()}`}
        actions={
          <Link className={buttonVariants({ variant: "secondary" })} to="/reports">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Reports
          </Link>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Investment thesis</CardTitle>
              <StatusBadge status={report.status} />
            </div>
            <CardDescription>Generated research summary.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="leading-7 text-foreground">{report.thesis}</p>
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Risks</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3 text-sm text-muted-foreground">
                {report.risks.map((risk) => (
                  <li className="rounded-md border border-border bg-muted p-3" key={risk}>
                    {risk}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Sources</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {report.sources.map((source) => (
                  <span
                    className="rounded-md border border-border bg-card px-2.5 py-1 text-sm"
                    key={source}
                  >
                    {source}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
