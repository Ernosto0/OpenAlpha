import { PlayCircle } from "lucide-react";
import { FormEvent, useState } from "react";

import { PageHeader } from "../components/page-header";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select } from "../components/ui/select";

export function AnalysisPage() {
  const [queuedSymbol, setQueuedSymbol] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setQueuedSymbol(String(formData.get("symbol") ?? "").toUpperCase());
  }

  return (
    <>
      <PageHeader
        eyebrow="Analysis"
        title="Run analysis"
        description="Start a new equity research run for a ticker symbol."
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,720px)_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>New report</CardTitle>
            <CardDescription>Set the scope for the initial analysis pass.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-5" onSubmit={handleSubmit}>
              <div className="grid gap-2">
                <Label htmlFor="symbol">Ticker symbol</Label>
                <Input
                  id="symbol"
                  name="symbol"
                  placeholder="AAPL"
                  required
                  type="text"
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="horizon">Horizon</Label>
                <Select id="horizon" name="horizon" defaultValue="medium">
                  <option value="short">Short term</option>
                  <option value="medium">Medium term</option>
                  <option value="long">Long term</option>
                </Select>
              </div>

              <label className="flex items-start gap-3 rounded-md border border-border bg-muted p-3 text-sm">
                <input
                  className="mt-1 h-4 w-4 rounded border-input text-primary focus:ring-ring"
                  defaultChecked
                  name="include-risks"
                  type="checkbox"
                />
                <span>
                  <span className="block font-medium">Include risk review</span>
                  <span className="text-muted-foreground">
                    Add competitive, valuation, and execution risks.
                  </span>
                </span>
              </label>

              <Button type="submit">
                <PlayCircle className="h-4 w-4" aria-hidden="true" />
                Run analysis
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Queue</CardTitle>
            <CardDescription>Latest run request.</CardDescription>
          </CardHeader>
          <CardContent>
            {queuedSymbol ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                {queuedSymbol} analysis is queued for the backend endpoint.
              </div>
            ) : (
              <div className="rounded-md border border-border bg-muted p-4 text-sm text-muted-foreground">
                No analysis queued.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
