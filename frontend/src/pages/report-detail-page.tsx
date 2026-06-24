import { ArrowLeft } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { ReportDashboard } from "../components/report/report-dashboard";
import { buttonVariants } from "../components/ui/button-styles";
import { Card, CardContent } from "../components/ui/card";
import { api, type ReportDetail } from "../lib/api";

export function ReportDetailPage() {
  const { id } = useParams();
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      setError("Report not found.");
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    api
      .getReport(id)
      .then((detail) => {
        if (!active) {
          return;
        }

        setReport(detail);
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setError("Unable to load report.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [id]);

  return (
    <>
      <div className="mb-6">
        <Link
          className={buttonVariants({
            variant: "secondary",
            className: "font-mono text-xs",
          })}
          to="/reports"
        >
          <ArrowLeft className="mr-2 h-3 w-3" aria-hidden="true" />
          Back To Reports
        </Link>
      </div>

      <PageHeader
        eyebrow="Report"
        title="Research Terminal"
        description="Comprehensive AI-generated equity research dashboard."
      />

      {loading ? (
        <Card className="bg-card shadow-panel">
          <CardContent className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            Loading report...
          </CardContent>
        </Card>
      ) : error || !report ? (
        <Card className="bg-card shadow-panel">
          <CardContent className="flex h-40 items-center justify-center text-sm text-destructive">
            {error ?? "Report not found."}
          </CardContent>
        </Card>
      ) : (
        <ReportDashboard report={report} />
      )}
    </>
  );
}
