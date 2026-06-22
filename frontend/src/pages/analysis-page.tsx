import { ExternalLink, PlayCircle } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../components/page-header";
import { AgentTimeline, type AgentRun } from "../components/shared/agent-timeline";
import { CostBreakdown } from "../components/shared/cost-breakdown";
import { DataQualityBar } from "../components/shared/data-quality-bar";
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
  HORIZON_OPTIONS,
  MARKET_OPTIONS,
  formatAgentName,
  formatOverallView,
  getModelOptionsForSelection,
  getProviderLabel,
  getModelsForProvider,
  toRiskBadgeLevel,
  type AnalysisProvider,
} from "../lib/analysis";
import {
  api,
  ApiError,
  type AnalysisAgentOutputResponse,
  type AnalysisEvent,
  type AnalysisRequest,
  type AnalysisRunDetailResponse,
  type ReportCostItem,
  type ReportDetail,
} from "../lib/api";
import { useAppSettings } from "../lib/settings-context";

const AGENT_ORDER = [
  "data_collector",
  "technical_agent",
  "news_sentiment_agent",
  "bull_case_agent",
  "bear_case_agent",
  "risk_review_agent",
  "thesis_agent",
  "report_writer_agent",
] as const;

const TERMINAL_RUN_STATUSES = new Set(["completed", "failed"]);
const TERMINAL_AGENT_STATUSES = new Set(["completed", "partial", "failed"]);

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

type FinalReportView = {
  title: string | null;
  symbol: string | null;
  companyName: string | null;
  overallView: string | null;
  confidence: number | null;
  horizon: string | null;
  executiveSummary: string | null;
  investmentThesis: string | null;
  baseCase: string | null;
  bullCaseSummary: string | null;
  bearCaseSummary: string | null;
  whatToWatch: string[];
  warnings: string[];
  disclaimer: string | null;
  reportMarkdown: string | null;
  riskLevel: string | null;
  riskScore: number | null;
  mainRisks: string[];
  invalidationConditions: string[];
  confidenceAdjustment: number | null;
  dataQualityScore: number | null;
  priceDataStatus: string | null;
  newsDataStatus: string | null;
  companyProfileStatus: string | null;
  missingData: string[];
  providers: string[];
  dataWarnings: string[];
  sources: Array<{
    name: string;
    provider: string;
    usedFor: string;
    url: string | null;
  }>;
};

export function AnalysisPage() {
  const { runId: routeRunId } = useParams();
  const { settings, isLoading: isSettingsLoading } = useAppSettings();
  const [formState, setFormState] = useState<AnalysisRequest>(DEFAULT_FORM_STATE);
  const [activeRunId, setActiveRunId] = useState<string | null>(routeRunId ?? null);
  const [selectedRequest, setSelectedRequest] = useState<AnalysisRequest | null>(null);
  const [runDetail, setRunDetail] = useState<AnalysisRunDetailResponse | null>(null);
  const [reportDetail, setReportDetail] = useState<ReportDetail | null>(null);
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRunLoading, setIsRunLoading] = useState(Boolean(routeRunId));
  const [isReportLoading, setIsReportLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [defaultsApplied, setDefaultsApplied] = useState(false);
  const eventKeysRef = useRef<Set<string>>(new Set());

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
    if (!routeRunId) {
      return;
    }

    setActiveRunId(routeRunId);
  }, [routeRunId]);

  useEffect(() => {
    if (!activeRunId) {
      return;
    }

    let cancelled = false;
    let latestStatus = "running";
    let pollTimer: number | null = null;
    let websocket: WebSocket | null = null;
    let websocketClosedIntentionally = false;

    setIsRunLoading(true);
    setRunError(null);
    setReportDetail(null);
    setReportError(null);
    setEvents([]);
    eventKeysRef.current = new Set();

    const clearPoll = () => {
      if (pollTimer !== null) {
        window.clearTimeout(pollTimer);
        pollTimer = null;
      }
    };

    const schedulePoll = (delay = 2500) => {
      if (cancelled || pollTimer !== null || TERMINAL_RUN_STATUSES.has(latestStatus)) {
        return;
      }

      pollTimer = window.setTimeout(async () => {
        pollTimer = null;
        const detail = await refreshRunDetail();
        if (!detail || !TERMINAL_RUN_STATUSES.has(detail.status)) {
          schedulePoll();
        }
      }, delay);
    };

    const mergeEvent = (event: AnalysisEvent) => {
      const key = [
        event.type,
        event.run_id,
        event.agent_name ?? "",
        event.timestamp,
        event.status ?? "",
      ].join(":");

      if (eventKeysRef.current.has(key)) {
        return;
      }

      eventKeysRef.current.add(key);
      setEvents((current) => [...current, event]);
    };

    const refreshRunDetail = async () => {
      try {
        const detail = await api.getAnalysisRun(activeRunId);
        if (cancelled) {
          return null;
        }

        latestStatus = detail.status;
        setRunDetail(detail);
        setRunError(null);
        setIsRunLoading(false);
        return detail;
      } catch {
        if (!cancelled) {
          setRunError("Unable to load analysis run.");
          setIsRunLoading(false);
          schedulePoll(1000);
        }
        return null;
      }
    };

    const connectWebSocket = () => {
      try {
        websocket = api.createAnalysisRunWebSocket(activeRunId);
      } catch {
        schedulePoll(1000);
        return;
      }

      websocket.onmessage = (message) => {
        if (cancelled) {
          return;
        }

        try {
          const event = JSON.parse(message.data) as AnalysisEvent;
          if (event.run_id !== activeRunId) {
            return;
          }

          if (event.status) {
            latestStatus = event.status;
          }

          mergeEvent(event);

          if (
            event.type === "agent_finished" ||
            event.type === "agent_failed" ||
            event.type === "analysis_completed" ||
            event.type === "analysis_failed"
          ) {
            void refreshRunDetail();
          }
        } catch {
          schedulePoll(1000);
        }
      };

      websocket.onerror = () => {
        schedulePoll(1000);
      };

      websocket.onclose = () => {
        if (cancelled || websocketClosedIntentionally || TERMINAL_RUN_STATUSES.has(latestStatus)) {
          return;
        }

        schedulePoll(1000);
      };
    };

    void refreshRunDetail().then((detail) => {
      if (cancelled) {
        return;
      }

      if (detail && TERMINAL_RUN_STATUSES.has(detail.status)) {
        return;
      }

      connectWebSocket();
    });

    return () => {
      cancelled = true;
      clearPoll();
      if (websocket) {
        websocketClosedIntentionally = true;
        websocket.close();
      }
    };
  }, [activeRunId]);

  useEffect(() => {
    const reportId = runDetail?.report_id;
    if (!reportId) {
      setReportDetail(null);
      setIsReportLoading(false);
      setReportError(null);
      return;
    }

    let active = true;
    setIsReportLoading(true);
    setReportError(null);

    api
      .getReport(reportId)
      .then((detail) => {
        if (!active) {
          return;
        }

        setReportDetail(detail);
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setReportError("Unable to load final report.");
      })
      .finally(() => {
        if (active) {
          setIsReportLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [runDetail?.report_id]);

  const modelOptions = getModelOptionsForSelection(
    formState.llm_provider,
    formState.llm_model,
  );
  const isSelectedProviderReady =
    formState.llm_provider === "openai"
      ? (settings?.providers.openai.api_key_configured ?? false)
      : formState.llm_provider === "claude"
        ? (settings?.providers.claude.api_key_configured ?? false)
        : formState.llm_provider === "gemini"
          ? (settings?.providers.gemini.api_key_configured ?? false)
          : true;
  const providerValidationMessage =
    !isSelectedProviderReady && formState.llm_provider !== "local"
      ? `Add a ${getProviderLabel(formState.llm_provider)} API key in Settings before running analysis with ${getProviderLabel(formState.llm_provider)}.`
      : null;

  const summarySymbol = runDetail?.symbol ?? selectedRequest?.symbol ?? "Not selected";
  const summaryHorizon = formatHorizon(runDetail?.horizon ?? selectedRequest?.horizon ?? null);
  const runStatus = runDetail?.status ?? (activeRunId ? "running" : "pending");
  const runStatusLabel = formatOverallView(runStatus);
  const timelineAgents = useMemo(
    () => buildTimelineAgents(runDetail, reportDetail, events),
    [events, reportDetail, runDetail],
  );
  const completedAgentCount = timelineAgents.filter((agent) =>
    TERMINAL_AGENT_STATUSES.has(agent.status),
  ).length;
  const partialAgentCount = timelineAgents.filter((agent) => agent.status === "partial").length;
  const finalReport = useMemo(
    () => parseFinalReport(reportDetail?.final_report ?? null),
    [reportDetail],
  );

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
    setRunError(null);
    setReportError(null);
    setIsSubmitting(true);

    const payload: AnalysisRequest = {
      ...formState,
      symbol: formState.symbol.trim().toUpperCase(),
      custom_question: formState.custom_question?.trim() || null,
    };

    try {
      const response = await api.runAnalysis(payload);
      setSelectedRequest(payload);
      setRunDetail(null);
      setReportDetail(null);
      setEvents([]);
      eventKeysRef.current = new Set();
      setActiveRunId(response.run_id);
    } catch (error) {
      if (error instanceof ApiError && error.detail) {
        setSubmitError(error.detail);
      } else {
        setSubmitError("Unable to start analysis run.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Analysis"
        title="Analysis Run"
        description="Launch a research run, monitor every agent, and review the final report in one workspace."
        actions={
          <Link
            className={buttonVariants({
              variant: "secondary",
              className: "hidden sm:inline-flex font-mono",
            })}
            to="/reports"
          >
            View Reports
          </Link>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="bg-card shadow-panel">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle>Research Parameters</CardTitle>
            <CardDescription>
              Configure the next structured equity research run.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form className="grid gap-6" onSubmit={handleSubmit}>
              <div className="grid gap-6 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="symbol">Symbol</Label>
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
                    onChange={(event) =>
                      updateField("market", event.target.value as AnalysisRequest["market"])
                    }
                  >
                    {MARKET_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="horizon">Time Horizon</Label>
                  <Select
                    id="horizon"
                    name="horizon"
                    value={formState.horizon}
                    onChange={(event) =>
                      updateField("horizon", event.target.value as AnalysisRequest["horizon"])
                    }
                  >
                    {HORIZON_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="depth">Analysis Depth</Label>
                  <Select
                    id="depth"
                    name="depth"
                    value={formState.depth}
                    onChange={(event) =>
                      updateField("depth", event.target.value as AnalysisRequest["depth"])
                    }
                  >
                    {DEPTH_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="provider">LLM Provider</Label>
                  <Select
                    id="provider"
                    name="provider"
                    value={formState.llm_provider}
                    onChange={(event) => handleProviderChange(event.target.value as AnalysisProvider)}
                  >
                    <option value="openai">OpenAI</option>
                    <option value="claude">Claude</option>
                    <option value="gemini">Gemini</option>
                    <option value="local">Ollama</option>
                  </Select>
                  {providerValidationMessage ? (
                    <p className="text-xs text-destructive">{providerValidationMessage}</p>
                  ) : null}
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

                <div className="grid gap-2">
                  <Label htmlFor="language">Language</Label>
                  <Select
                    id="language"
                    name="language"
                    value={formState.language}
                    onChange={(event) =>
                      updateField("language", event.target.value as AnalysisRequest["language"])
                    }
                  >
                    <option value="en">English</option>
                    <option value="tr">Turkish</option>
                  </Select>
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="focus">Optional Research Focus</Label>
                <Input
                  id="focus"
                  name="focus"
                  placeholder="Focus on margins, product cycle risk, or valuation."
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
                  disabled={
                    isSubmitting ||
                    isSettingsLoading ||
                    !isSelectedProviderReady ||
                    (activeRunId !== null && !TERMINAL_RUN_STATUSES.has(runStatus))
                  }
                >
                  <PlayCircle className="mr-2 h-4 w-4" aria-hidden="true" />
                  {isSubmitting ? "Starting Analysis..." : "Run Analysis"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="bg-card shadow-panel">
            <CardHeader className="border-b border-border pb-4">
              <CardTitle>Run Summary</CardTitle>
              <CardDescription>Selected inputs, run state, and completion progress.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 pt-6">
              <SummaryRow label="Symbol" value={summarySymbol} />
              <SummaryRow label="Horizon" value={summaryHorizon} />
              <SummaryRow
                label="Run Status"
                value={
                  <StatusBadge
                    status={runStatusLabel}
                    variant={statusVariant(runStatus)}
                  />
                }
              />
              <SummaryRow
                label="Agent Progress"
                value={`${completedAgentCount}/${AGENT_ORDER.length}`}
              />
              <SummaryRow
                label="Partial Agents"
                value={String(partialAgentCount)}
              />
              <SummaryRow
                label="Cost So Far"
                value={formatUsd(runDetail?.total_cost_usd ?? 0)}
              />
              {activeRunId ? <SummaryRow label="Run ID" value={activeRunId.slice(0, 8)} /> : null}
              {runDetail?.error_message ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {runDetail.error_message}
                </div>
              ) : null}
              {runError ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {runError}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="bg-card shadow-panel">
            <CardHeader className="border-b border-border pb-4">
              <CardTitle>Report</CardTitle>
              <CardDescription>Final report becomes available here as soon as it is persisted.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {runDetail?.report_id ? (
                <Link
                  className={buttonVariants({
                    variant: "secondary",
                    className: "w-full justify-center font-mono",
                  })}
                  to={`/reports/${runDetail.report_id}`}
                >
                  <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                  Open Report Detail
                </Link>
              ) : (
                <div className="text-sm text-muted-foreground">
                  Waiting for the report writer to finish.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="bg-card shadow-panel">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle>Execution Trace</CardTitle>
            <CardDescription>Live agent progression with partial and terminal states.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            {isRunLoading ? (
              <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-sm text-muted-foreground">
                Loading run status...
              </div>
            ) : !activeRunId ? (
              <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-sm text-muted-foreground">
                Start a run to populate the timeline.
              </div>
            ) : (
              <AgentTimeline agents={timelineAgents} />
            )}
          </CardContent>
        </Card>

        <Card className="bg-card shadow-panel">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle>Run Telemetry</CardTitle>
            <CardDescription>Cost and output telemetry for the current report.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-6">
            {reportDetail?.cost_breakdown.items.length ? (
              <CostBreakdown
                items={reportDetail.cost_breakdown.items.map((item) => ({
                  label: formatAgentName(item.agent_name),
                  model: `${item.provider}/${item.model}`,
                  inputTokens: item.input_tokens,
                  outputTokens: item.output_tokens,
                  cost: item.cost_usd,
                }))}
              />
            ) : (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                Cost breakdown will appear after agent traces are persisted.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-6">
        <Card className="bg-card shadow-panel">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle>Final Report</CardTitle>
            <CardDescription>Inline final report rendered from the persisted backend result.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 pt-6">
            {isReportLoading ? (
              <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-sm text-muted-foreground">
                Loading final report...
              </div>
            ) : reportError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {reportError}
              </div>
            ) : !reportDetail || !finalReport ? (
              <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-sm text-muted-foreground">
                Final report will appear when the run completes.
              </div>
            ) : (
              <>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <h2 className="text-2xl font-semibold">
                      {finalReport.title ?? `${reportDetail.symbol} Equity Research Report`}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {finalReport.companyName ?? reportDetail.symbol} · {new Date(reportDetail.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <StatusBadge
                      status={formatOverallView(finalReport.overallView ?? reportDetail.overall_view)}
                      variant={viewVariant(finalReport.overallView ?? reportDetail.overall_view)}
                    />
                    <RiskBadge level={toRiskBadgeLevel(finalReport.riskLevel ?? reportDetail.risk_level)} />
                    <StatusBadge
                      status={formatHorizon(finalReport.horizon ?? reportDetail.horizon)}
                      variant="secondary"
                    />
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-4">
                  <MetricPanel
                    label="Confidence"
                    value={formatPercent(finalReport.confidence)}
                  />
                  <MetricPanel
                    label="Risk Score"
                    value={finalReport.riskScore != null ? `${Math.round(finalReport.riskScore)}/100` : "-"}
                  />
                  <MetricPanel
                    label="Total Cost"
                    value={formatUsd(reportDetail.cost_breakdown.total_cost_usd)}
                  />
                  <MetricPanel
                    label="Data Quality"
                    value={
                      finalReport.dataQualityScore != null
                        ? `${Math.round(finalReport.dataQualityScore * 100)}%`
                        : "-"
                    }
                  />
                </div>

                {finalReport.dataQualityScore != null ? (
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold">Data Quality</h3>
                    <DataQualityBar score={Math.round(finalReport.dataQualityScore * 100)} />
                    <p className="text-sm text-muted-foreground">
                      Price: {finalReport.priceDataStatus ?? "unknown"} · News: {finalReport.newsDataStatus ?? "unknown"} · Profile: {finalReport.companyProfileStatus ?? "unknown"}
                    </p>
                  </div>
                ) : null}

                <ReportSection
                  title="Executive Summary"
                  body={finalReport.executiveSummary}
                />
                <ReportSection
                  title="Investment Thesis"
                  body={finalReport.investmentThesis}
                />
                <ReportSection title="Base Case" body={finalReport.baseCase} />
                <ReportSection
                  title="Bull Case"
                  body={finalReport.bullCaseSummary}
                />
                <ReportSection
                  title="Bear Case"
                  body={finalReport.bearCaseSummary}
                />

                {finalReport.whatToWatch.length ? (
                  <ListSection title="What To Watch" items={finalReport.whatToWatch} />
                ) : null}
                {finalReport.mainRisks.length ? (
                  <ListSection title="Main Risks" items={finalReport.mainRisks} />
                ) : null}
                {finalReport.invalidationConditions.length ? (
                  <ListSection
                    title="Invalidation Conditions"
                    items={finalReport.invalidationConditions}
                  />
                ) : null}
                {finalReport.missingData.length ? (
                  <ListSection title="Missing Data" items={finalReport.missingData} />
                ) : null}
                {finalReport.providers.length ? (
                  <ListSection title="Providers" items={finalReport.providers} />
                ) : null}
                {finalReport.warnings.length ? (
                  <ListSection title="Warnings" items={finalReport.warnings} />
                ) : null}
                {finalReport.dataWarnings.length ? (
                  <ListSection title="Data Warnings" items={finalReport.dataWarnings} />
                ) : null}

                {finalReport.sources.length ? (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold">Sources</h3>
                    <div className="grid gap-3 md:grid-cols-2">
                      {finalReport.sources.map((source) => (
                        <div
                          key={`${source.provider}-${source.name}-${source.usedFor}`}
                          className="rounded-lg border border-border bg-muted/20 p-3"
                        >
                          <p className="font-medium">{source.name}</p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {source.provider} · {source.usedFor}
                          </p>
                          {source.url ? (
                            <a
                              className="mt-2 inline-flex text-sm font-mono text-primary underline-offset-4 hover:underline"
                              href={source.url}
                              rel="noreferrer"
                              target="_blank"
                            >
                              Open Source
                            </a>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {finalReport.reportMarkdown ? (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold">Rendered Report</h3>
                    <div className="rounded-lg border border-border bg-muted/20 p-4">
                      <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
                        {finalReport.reportMarkdown}
                      </pre>
                    </div>
                  </div>
                ) : null}

                {finalReport.disclaimer ? (
                  <div className="rounded-lg border border-border bg-muted/20 p-4 text-xs leading-6 text-muted-foreground">
                    <strong>Disclaimer:</strong> {finalReport.disclaimer}
                  </div>
                ) : null}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function SummaryRow({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-mono">{value}</span>
    </div>
  );
}

function MetricPanel({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4">
      <p className="text-xs font-mono uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-xl font-semibold">{value}</p>
    </div>
  );
}

function ReportSection({
  title,
  body,
}: {
  title: string;
  body: string | null;
}) {
  if (!body) {
    return null;
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="text-sm leading-6 text-foreground">{body}</p>
    </div>
  );
}

function ListSection({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="space-y-2 text-sm text-foreground">
        {items.map((item) => (
          <li key={item} className="rounded-lg border border-border bg-muted/20 px-3 py-2">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function buildTimelineAgents(
  runDetail: AnalysisRunDetailResponse | null,
  reportDetail: ReportDetail | null,
  events: AnalysisEvent[],
): AgentRun[] {
  const outputsByAgent = new Map<string, AnalysisAgentOutputResponse>();
  for (const output of runDetail?.agent_outputs ?? []) {
    outputsByAgent.set(output.agent_name, output);
  }

  const lastEventByAgent = new Map<string, AnalysisEvent>();
  for (const event of events) {
    if (!event.agent_name) {
      continue;
    }

    lastEventByAgent.set(event.agent_name, event);
  }

  const costByAgent = new Map<string, ReportCostItem>();
  for (const item of reportDetail?.cost_breakdown.items ?? []) {
    costByAgent.set(item.agent_name, item);
  }

  return AGENT_ORDER.map((agentName) => {
    const output = outputsByAgent.get(agentName);
    const lastEvent = lastEventByAgent.get(agentName);
    const costTrace = costByAgent.get(agentName);
    const status = mapTimelineStatus(output?.status ?? lastEvent?.status ?? "pending");

    return {
      id: agentName,
      name: formatAgentName(agentName),
      status,
      duration: formatDuration(output?.started_at ?? lastEvent?.timestamp ?? null, output?.finished_at ?? null, status),
      provider: costTrace?.provider,
      model: costTrace?.model,
      cost:
        output?.cost_usd && output.cost_usd > 0
          ? formatUsd(output.cost_usd)
          : costTrace
            ? formatUsd(costTrace.cost_usd)
            : undefined,
    };
  });
}

function mapTimelineStatus(status: string): AgentRun["status"] {
  switch (status) {
    case "completed":
      return "completed";
    case "partial":
      return "partial";
    case "failed":
      return "failed";
    case "running":
      return "running";
    default:
      return "pending";
  }
}

function formatDuration(
  startedAt: string | null,
  finishedAt: string | null,
  status: AgentRun["status"],
) {
  if (!startedAt || status === "pending") {
    return undefined;
  }

  const start = new Date(startedAt).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  return `${seconds}s`;
}

function parseFinalReport(value: Record<string, unknown> | null): FinalReportView | null {
  if (!value) {
    return null;
  }

  const riskSection = getObject(value.risk_section);
  const dataQuality = getObject(value.data_quality_section);
  const sourceSection = getObjectArray(value.source_section);

  return {
    title: getString(value.title),
    symbol: getString(value.symbol),
    companyName: getString(value.company_name),
    overallView: getString(value.overall_view),
    confidence: getNumber(value.confidence),
    horizon: getString(value.horizon),
    executiveSummary: getString(value.executive_summary),
    investmentThesis: getString(value.investment_thesis),
    baseCase: getString(value.base_case),
    bullCaseSummary: getString(value.bull_case_summary),
    bearCaseSummary: getString(value.bear_case_summary),
    whatToWatch: getStringArray(value.what_to_watch),
    warnings: getStringArray(value.warnings),
    disclaimer: getString(value.disclaimer),
    reportMarkdown: getString(value.report_markdown),
    riskLevel: getString(riskSection?.risk_level),
    riskScore: getNumber(riskSection?.risk_score),
    mainRisks: getStringArray(riskSection?.main_risks),
    invalidationConditions: getStringArray(riskSection?.invalidation_conditions),
    confidenceAdjustment: getNumber(riskSection?.confidence_adjustment),
    dataQualityScore: getNumber(dataQuality?.data_quality_score),
    priceDataStatus: getString(dataQuality?.price_data_status),
    newsDataStatus: getString(dataQuality?.news_data_status),
    companyProfileStatus: getString(dataQuality?.company_profile_status),
    missingData: getStringArray(dataQuality?.missing_data),
    providers: getStringArray(dataQuality?.providers),
    dataWarnings: getStringArray(dataQuality?.warnings),
    sources: sourceSection.map((source) => ({
      name: getString(source.name) ?? "Unknown source",
      provider: getString(source.provider) ?? "Unknown provider",
      usedFor: getString(source.used_for) ?? "Research",
      url: getString(source.url),
    })),
  };
}

function getString(value: unknown) {
  return typeof value === "string" ? value : null;
}

function getNumber(value: unknown) {
  return typeof value === "number" ? value : null;
}

function getStringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function getObject(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  return value as Record<string, unknown>;
}

function getObjectArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(getObject(item)))
    : [];
}

function formatUsd(value: number) {
  return `$${value.toFixed(4)}`;
}

function formatPercent(value: number | null) {
  if (value == null) {
    return "-";
  }

  return `${Math.round(value * 100)}%`;
}

function formatHorizon(value: string | null) {
  if (!value) {
    return "Not selected";
  }

  const option = HORIZON_OPTIONS.find((item) => item.value === value);
  return option?.label ?? value;
}

function statusVariant(status: string) {
  if (status === "failed") {
    return "destructive" as const;
  }

  if (status === "completed") {
    return "success" as const;
  }

  return "info" as const;
}

function viewVariant(view: string) {
  return view.includes("bear") ? "warning" : "success";
}
