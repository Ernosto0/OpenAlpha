import { Search } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { StatusBadge } from "../components/status-badge";
import { buttonVariants } from "../components/ui/button-styles";
import { Card, CardContent } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { reportHistory } from "../data/reports";

export function ReportsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Reports"
        title="Report history"
        description="Review generated and draft research reports."
      />

      <div className="flex max-w-md items-center gap-2">
        <div className="relative w-full">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input className="pl-9" placeholder="Search reports" type="search" />
        </div>
      </div>

      <section className="grid gap-3">
        {reportHistory.map((report) => (
          <Card key={report.id}>
            <CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{report.symbol}</span>
                  <StatusBadge status={report.status} />
                </div>
                <h2 className="truncate text-base font-medium">{report.title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {new Date(report.createdAt).toLocaleString()}
                </p>
              </div>
              <Link
                className={buttonVariants({
                  className: "w-full md:w-auto",
                  variant: "secondary",
                })}
                to={`/reports/${report.id}`}
              >
                Open report
              </Link>
            </CardContent>
          </Card>
        ))}
      </section>
    </>
  );
}
