import {
  Activity,
  CheckCircle2,
  Clock3,
  PlayCircle,
  Server,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { MetricCard } from "../components/shared/metric-card";
import { RiskBadge, StatusBadge } from "../components/shared/status-badges";
import { Button } from "../components/ui/button";
import { buttonVariants } from "../components/ui/button-styles";
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
import {
  DEFAULT_MODEL,
  DEFAULT_PROVIDER,
  DEPTH_OPTIONS,
  MARKET_OPTIONS,
  HORIZON_OPTIONS,
  formatOverallView,
  getModelOptionsForSelection,
  getProviderLabel,
  getModelsForProvider,
  toRiskBadgeLevel,
  type AnalysisProvider,
} from "../lib/analysis";
import {
  api,
  type AnalysisRequest,
  type HealthResponse,
  type ReportSummary,
} from "../lib/api";
import { useAppSettings } from "../lib/settings-context";

const DEFAULT_FORM_STATE: AnalysisRequest = {
  symbol: "",
  market: "US",
  horizon: "3m",
  depth: "standard",
  language: "en",
  llm_provider: DEFAULT_PROVIDER,
  llm_model: DEFAULT_MODEL,
  custom_question: null,
};

export function DashboardPage() {
  const navigate = useNavigate();
  const { settings } = useAppSettings();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [reportsLoading, setReportsLoading] = useState(true);
  const [reportsError, setReportsError] = useState<string | null>(null);
  const [formState, setFormState] = useState<AnalysisRequest>(DEFAULT_FORM_STATE);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [defaultsApplied, setDefaultsApplied] = useState(false);

  useEffect(() => {
    if (!settings || defaultsApplied) {
      return;
    }

    setFormState((current) => ({
      ...current,
      llm_provider: settings.default_provider,
      llm_model: settings.default_model,
    }));
    setDefaultsApplied(true);
  }, [defaultsApplied, settings]);

  useEffect(() => {
    api
      .getHealth()
      .then(setHealth)
      .catch(() => setHealthError("API unavailable"));
  }, []);

  useEffect(() => {
    let active = true;

    api
      .listReports()
      .then((data) => {
        if (!active) {
          return;
        }

        setReports(data);
        setReportsError(null);
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setReportsError("Unable to load recent reports.");
      })
      .finally(() => {
        if (active) {
          setReportsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const modelOptions = getModelOptionsForSelection(
    formState.llm_provider,
    formState.llm_model,
  );
  const visibleReports = reports.slice(0, 6);
  const selectedProviderReady =
    formState.llm_provider === "openai"
      ? (settings?.providers.openai.api_key_configured ?? false)
      : formState.llm_provider === "claude"
        ? (settings?.providers.claude.api_key_configured ?? false)
        : formState.llm_provider === "gemini"
          ? (settings?.providers.gemini.api_key_configured ?? false)
          : true;

  function updateField<K extends keyof AnalysisRequest>(
    field: K,
    value: AnalysisRequest[K],
  ) {
    setFormState((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleProviderChange(provider: AnalysisProvider) {
    const nextModel = getModelsForProvider(provider)[0]?.value ?? DEFAULT_MODEL;

    setFormState((current) => ({
      ...current,
      llm_provider: provider,
      llm_model: nextModel,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setIsSubmitting(true);

    try {
      const response = await api.runAnalysis({
        ...formState,
        symbol: formState.symbol.trim().toUpperCase(),
        custom_question: formState.custom_question?.trim() || null,
      });
      navigate(`/analysis/${response.run_id}`);
    } catch {
      setSubmitError("Unable to start analysis run.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Dashboard"
        title="Research Workstation"
        description="Launch new equity research runs and review the latest completed reports."
        actions={
          <Link
            className={buttonVariants({
              variant: "primary",
              className:
                "hidden sm:inline-flex bg-primary text-primary-foreground font-semibold font-mono",
            })}
            to="/reports"
          >
            View All Reports
          </Link>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={Server}
          label="API Status"
          value={health?.status ?? healthError ?? "Checking"}
          detail={health?.service ?? "http://127.0.0.1:8000"}
        />
        <MetricCard
          icon={Activity}
          label="Run Status"
          value={isSubmitting ? "Starting" : "Ready"}
          detail="Dashboard launcher"
        />
        <MetricCard
          icon={CheckCircle2}
          label="Completed Reports"
          value={String(reports.length)}
          detail="Backend report store"
        />
        <MetricCard
          icon={Clock3}
          label="Last Refresh"
          value={reportsLoading ? "Loading" : "Synced"}
          detail="Recent reports"
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="bg-card shadow-panel">
          <CardHeader className="pb-4 border-b border-border">
            <CardTitle className="text-lg">Run Analysis</CardTitle>
            <CardDescription>
              Configure the next research pass and launch it directly from the dashboard.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form className="grid gap-6" onSubmit={handleSubmit}>
              <div className="grid gap-6 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="symbol">Stock Symbol</Label>
                  <Input
                    id="symbol"
                    name="symbol"
                    placeholder="AAPL"
                    required
                    className="font-mono"
                    value={formState.symbol}
                    onChange={(event) => updateField("symbol", event.target.value.toUpperCase())}
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="market">Market</Label>
                  <Select
                    id="market"
                    name="market"
                    value={formState.market}
                    onChange={(event) => updateField("market", event.target.value as AnalysisRequest["market"])}
                  >
                    {MARKET_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="horizon">Horizon</Label>
                  <Select
                    id="horizon"
                    name="horizon"
                    value={formState.horizon}
                    onChange={(event) => updateField("horizon", event.target.value as AnalysisRequest["horizon"])}
                  >
                    {HORIZON_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="depth">Depth</Label>
                  <Select
                    id="depth"
                    name="depth"
                    value={formState.depth}
                    onChange={(event) => updateField("depth", event.target.value as AnalysisRequest["depth"])}
                  >
                    {DEPTH_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="provider">Model Provider</Label>
                  <Select
                    id="provider"
                    name="provider"
                    value={formState.llm_provider}
                    onChange={(event) => handleProviderChange(event.target.value as AnalysisProvider)}
                  >
                    <option value="openai">OpenAI</option>
                    <option value="claude">Claude</option>
                    <option value="gemini">Gemini</option>
                    <option value="ollama">Ollama</option>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="model">Model</Label>
                  <Select
                    id="model"
                    name="model"
                    value={formState.llm_model}
                    onChange={(event) => updateField("llm_model", event.target.value)}
                  >
                    {modelOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="focus">
                  Optional Research Focus
                </Label>
                <Input
                  id="focus"
                  name="focus"
                  placeholder="Focus on margin durability, product cycle risk, or valuation."
                  value={formState.custom_question ?? ""}
                  onChange={(event) => updateField("custom_question", event.target.value)}
                />
              </div>

              {submitError ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {submitError}
                </div>
              ) : null}

              <div className="pt-2">
                <Button
                  type="submit"
                  className="w-full sm:w-auto font-semibold font-mono bg-primary text-primary-foreground"
                  disabled={isSubmitting || !selectedProviderReady}
                >
                  <PlayCircle className="h-4 w-4 mr-2" aria-hidden="true" />
                  {isSubmitting ? "Starting Analysis..." : "Run Analysis"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="bg-card shadow-panel">
            <CardHeader className="pb-3 border-b border-border">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-lg">Recent Reports</CardTitle>
                  <CardDescription>Latest completed analysis runs.</CardDescription>
                </div>
                <Link
                  className={buttonVariants({
                    variant: "secondary",
                    className: "h-8 px-3 text-xs font-mono",
                  })}
                  to="/reports"
                >
                  All Reports
                </Link>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {reportsLoading ? (
                <div className="p-4 text-sm text-muted-foreground">
                  Loading recent reports...
                </div>
              ) : reportsError ? (
                <div className="p-4 text-sm text-destructive">{reportsError}</div>
              ) : visibleReports.length === 0 ? (
                <div className="p-4 text-sm text-muted-foreground">
                  No reports available yet.
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {visibleReports.map((report) => {
                    const view = formatOverallView(report.overall_view);

                    return (
                      <Link
                        className="flex items-center justify-between gap-4 p-4 hover:bg-muted/30 transition-colors"
                        key={report.id}
                        to={`/reports/${report.id}`}
                      >
                        <div className="flex min-w-0 items-center gap-4">
                          <div className="h-10 w-10 shrink-0 flex items-center justify-center rounded-md bg-muted font-bold tracking-tight">
                            {report.symbol}
                          </div>
                          <div className="min-w-0">
                            <p className="font-semibold">{report.symbol} Analysis</p>
                            <p className="truncate text-sm text-muted-foreground">
                              {new Date(report.created_at).toLocaleString()} · {report.horizon}
                            </p>
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <StatusBadge
                            status={view}
                            variant={view.includes("Bear") ? "warning" : "success"}
                          />
                          <RiskBadge level={toRiskBadgeLevel(report.risk_level)} />
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card shadow-panel">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                System Status
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 font-mono text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Local DB</span>
                <span className="text-success">Connected</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">OpenAI Key</span>
                <span
                  className={
                    settings?.providers.openai.api_key_configured
                      ? "text-success"
                      : "text-muted-foreground"
                  }
                >
                  {settings?.providers.openai.api_key_configured ? "Configured" : "Missing"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Claude Key</span>
                <span
                  className={
                    settings?.providers.claude.api_key_configured
                      ? "text-success"
                      : "text-muted-foreground"
                  }
                >
                  {settings?.providers.claude.api_key_configured ? "Configured" : "Missing"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Gemini Key</span>
                <span
                  className={
                    settings?.providers.gemini.api_key_configured
                      ? "text-success"
                      : "text-muted-foreground"
                  }
                >
                  {settings?.providers.gemini.api_key_configured ? "Configured" : "Missing"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Ollama</span>
                <span className="text-muted-foreground">
                  {settings?.providers.ollama.model ?? "Not set"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Default Runtime</span>
                <span className="text-success">
                  {settings ? `${getProviderLabel(settings.default_provider)} / ${settings.default_model}` : "Loading"}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </>
  );
}
