import type { ReportDetail } from "./api";
import {
  formatAgentName,
  formatOverallView,
  formatRiskLevel,
  getProviderLabel,
  HORIZON_OPTIONS,
} from "./analysis";

export type ReportBadgeVariant =
  | "default"
  | "secondary"
  | "destructive"
  | "success"
  | "warning"
  | "info";

export type ReportStatusValue = {
  label: string;
  variant: ReportBadgeVariant;
};

export type FinalReportView = {
  title: string | null;
  symbol: string | null;
  companyName: string | null;
  createdAt: string | null;
  currentPrice: number | null;
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
  fundamentalsStatus: string | null;
  missingData: string[];
  providers: string[];
  dataWarnings: string[];
  sources: Array<{
    name: string;
    type: string | null;
    provider: string;
    usedFor: string;
    url: string | null;
  }>;
  agentSummaries: {
    technical: string | null;
    newsSentiment: string | null;
    bullCase: string | null;
    bearCase: string | null;
    riskReview: string | null;
  };
};

export type ScenarioCardView = {
  id: "bear" | "base" | "bull";
  label: string;
  title: string;
  summary: string;
  condition: string | null;
};

export type WatchTriggerView = {
  id: string;
  title: string;
  description: string | null;
  whyItMatters: string | null;
  status: string | null;
};

export type EvidenceSignalView = {
  title: string;
  body: string | null;
  meta: string | null;
};

export type EvidenceGroupView = {
  id: string;
  title: string;
  tone: ReportBadgeVariant;
  items: EvidenceSignalView[];
};

export type PriceLevelView = {
  kind: "support" | "resistance";
  price: number;
  reason: string | null;
  strength: string | null;
};

type TechnicalLevelRecord = {
  price: number;
  reason: string | null;
  strength: string | null;
};

export function parseFinalReport(report: ReportDetail | null): FinalReportView | null {
  if (!report?.final_report || typeof report.final_report !== "object") {
    return null;
  }

  const value = report.final_report as Record<string, unknown>;
  const riskSection = getObject(value.risk_section);
  const dataQuality = getObject(value.data_quality_section);
  const sourceSection = getObjectArray(value.source_section);
  const agentSummaries = getObject(value.agent_summaries);
  const collectorDataQuality = getCollectorDataQuality(report);

  return {
    title: getString(value.title),
    symbol: getString(value.symbol),
    companyName: getString(value.company_name),
    createdAt: getString(value.created_at),
    currentPrice: getNumber(value.latest_close),
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
    dataQualityScore:
      getNumber(dataQuality?.data_quality_score) ??
      report.data_quality?.data_quality_score ??
      null,
    priceDataStatus:
      getString(dataQuality?.price_data_status) ??
      report.data_quality?.price_data_status ??
      null,
    newsDataStatus:
      getString(dataQuality?.news_data_status) ??
      report.data_quality?.news_data_status ??
      null,
    companyProfileStatus:
      getString(dataQuality?.company_profile_status) ??
      report.data_quality?.company_profile_status ??
      null,
    fundamentalsStatus:
      getString(dataQuality?.fundamentals_status) ??
      getString(collectorDataQuality?.fundamentals_status) ??
      null,
    missingData: dedupeStrings([
      ...getStringArray(dataQuality?.missing_data),
      ...(report.data_quality?.missing_data ?? []),
    ]),
    providers: dedupeStrings([
      ...getStringArray(dataQuality?.providers),
      ...(report.data_quality?.providers ?? []),
    ]),
    dataWarnings: dedupeStrings([
      ...getStringArray(dataQuality?.warnings),
      ...(report.data_quality?.warnings ?? []),
    ]),
    sources: sourceSection.map((source) => ({
      name: getString(source.name) ?? "Unknown source",
      type: getString(source.type),
      provider: getString(source.provider) ?? "Unknown provider",
      usedFor: getString(source.used_for) ?? "Research",
      url: getString(source.url),
    })),
    agentSummaries: {
      technical: getString(agentSummaries?.technical),
      newsSentiment: getString(agentSummaries?.news_sentiment),
      bullCase: getString(agentSummaries?.bull_case),
      bearCase: getString(agentSummaries?.bear_case),
      riskReview: getString(agentSummaries?.risk_review),
    },
  };
}

export function buildScenarioCards(
  report: ReportDetail | null,
  finalReport: FinalReportView | null,
): ScenarioCardView[] {
  if (!finalReport) {
    return [];
  }

  const bullOutput = getObject(getAgentOutput(report, "bull_case_agent")?.output_json);
  const bearOutput = getObject(getAgentOutput(report, "bear_case_agent")?.output_json);

  const cards: ScenarioCardView[] = [
    {
      id: "bear",
      label: "Bear Case",
      title: "Downside path",
      summary: finalReport.bearCaseSummary ?? "",
      condition:
        getStringArray(bearOutput?.downside_conditions)[0] ??
        finalReport.mainRisks[0] ??
        null,
    },
    {
      id: "base",
      label: "Base Case",
      title: "Central path",
      summary: finalReport.baseCase ?? "",
      condition:
        finalReport.whatToWatch[0] ??
        finalReport.invalidationConditions[0] ??
        null,
    },
    {
      id: "bull",
      label: "Bull Case",
      title: "Upside path",
      summary: finalReport.bullCaseSummary ?? "",
      condition:
        getStringArray(bullOutput?.upside_conditions)[0] ??
        finalReport.whatToWatch[1] ??
        null,
    },
  ];

  return cards.filter((item) => item.summary.trim().length > 0);
}

export function buildWatchTriggers(finalReport: FinalReportView | null): WatchTriggerView[] {
  return (finalReport?.whatToWatch ?? []).map((item, index) => {
    const parts = splitDescriptor(item);
    return {
      id: `${index}-${item}`,
      title: parts.title,
      description: parts.description,
      whyItMatters: null,
      status: null,
    };
  });
}

export function buildEvidenceGroups(
  report: ReportDetail | null,
  finalReport: FinalReportView | null,
): EvidenceGroupView[] {
  if (!report || !finalReport) {
    return [];
  }

  const technical = getObject(getAgentOutput(report, "technical_agent")?.output_json);
  const news = getObject(getAgentOutput(report, "news_sentiment_agent")?.output_json);

  const technicalSignals: EvidenceSignalView[] = [];
  const technicalSummary = getString(technical?.summary) ?? finalReport.agentSummaries.technical;
  if (technicalSummary) {
    technicalSignals.push({
      title: "Technical summary",
      body: technicalSummary,
      meta: null,
    });
  }

  for (const signal of getStringArray(technical?.key_signals).slice(0, 3)) {
    technicalSignals.push({ title: signal, body: null, meta: "Signal" });
  }

  for (const level of buildPriceLevels(report).slice(0, 2)) {
    technicalSignals.push({
      title: `${capitalize(level.kind) ?? level.kind} ${formatPrice(level.price)}`,
      body: level.reason,
      meta: level.strength ? capitalize(level.strength) : null,
    });
  }

  const newsSignals: EvidenceSignalView[] = [];
  const sentimentSummary =
    getString(news?.sentiment_summary) ?? finalReport.agentSummaries.newsSentiment;
  if (sentimentSummary) {
    newsSignals.push({
      title: "News summary",
      body: sentimentSummary,
      meta: null,
    });
  }

  for (const item of getObjectArray(news?.important_news).slice(0, 3)) {
    newsSignals.push({
      title: getString(item.title) ?? "News item",
      body: getString(item.summary),
      meta: [
        getString(item.source),
        capitalize(getString(item.sentiment)),
        capitalize(getString(item.relevance)),
      ]
        .filter((part): part is string => Boolean(part))
        .join(" / "),
    });
  }

  const limitations: EvidenceSignalView[] = [
    ...finalReport.dataWarnings.map((warning) => ({
      title: warning,
      body: null,
      meta: "Warning",
    })),
    ...finalReport.missingData.map((item) => ({
      title: item,
      body: null,
      meta: "Missing data",
    })),
    ...finalReport.warnings.map((warning) => ({
      title: warning,
      body: null,
      meta: "Report warning",
    })),
  ].slice(0, 4);

  const riskSignals: EvidenceSignalView[] = [
    ...finalReport.mainRisks.map((risk) => ({
      title: risk,
      body: null,
      meta: "Main risk",
    })),
    ...finalReport.invalidationConditions.map((item) => ({
      title: item,
      body: null,
      meta: "Invalidation",
    })),
  ].slice(0, 4);

  const groups: EvidenceGroupView[] = [
    {
      id: "technical",
      title: "Technical Signals",
      tone: "info",
      items: technicalSignals,
    },
    {
      id: "news",
      title: "News Signals",
      tone: "info",
      items: newsSignals,
    },
    {
      id: "limitations",
      title: "Data Limitations",
      tone: "warning",
      items: limitations,
    },
    {
      id: "risk",
      title: "Risk Signals",
      tone: "destructive",
      items: riskSignals,
    },
  ];

  return groups.filter((group) => group.items.length > 0);
}

export function buildPriceLevels(report: ReportDetail | null): PriceLevelView[] {
  const technical = getObject(getAgentOutput(report, "technical_agent")?.output_json);
  const supports = getTechnicalLevels(technical?.support_levels).map((level) => ({
    kind: "support" as const,
    ...level,
  }));
  const resistances = getTechnicalLevels(technical?.resistance_levels).map((level) => ({
    kind: "resistance" as const,
    ...level,
  }));
  return [...supports, ...resistances].slice(0, 6);
}

export function buildPrimaryModel(report: ReportDetail | null) {
  if (!report) {
    return null;
  }

  const preferredAgentNames = ["report_writer_agent", "thesis_agent", "risk_review_agent"];
  const preferredItem = preferredAgentNames
    .map((agentName) => report.cost_breakdown.items.find((item) => item.agent_name === agentName))
    .find((item): item is ReportDetail["cost_breakdown"]["items"][number] => Boolean(item));
  const fallbackItem =
    [...report.cost_breakdown.items]
      .reverse()
      .find((item) => item.model && item.provider && item.provider !== "deterministic") ??
    report.cost_breakdown.items[report.cost_breakdown.items.length - 1];

  const item = preferredItem ?? fallbackItem;
  if (!item) {
    return null;
  }

  return {
    provider: item.provider,
    providerLabel: getProviderLabel(item.provider),
    model: item.model,
    label: `${getProviderLabel(item.provider)} / ${item.model}`,
  };
}

export function getViewStatus(view: string | null | undefined): ReportStatusValue {
  if (!view) {
    return { label: "Unknown", variant: "secondary" };
  }

  if (view.includes("insufficient")) {
    return { label: formatOverallView(view), variant: "secondary" };
  }

  if (view.includes("bear")) {
    return { label: formatOverallView(view), variant: "warning" };
  }

  if (view.includes("neutral")) {
    return { label: formatOverallView(view), variant: "info" };
  }

  return { label: formatOverallView(view), variant: "success" };
}

export function getConfidenceStatus(confidence: number | null | undefined): ReportStatusValue {
  if (confidence == null) {
    return { label: "Unknown", variant: "secondary" };
  }

  const percentage = Math.round(confidence * 100);
  if (confidence >= 0.75) {
    return { label: `High / ${percentage}%`, variant: "success" };
  }

  if (confidence >= 0.5) {
    return { label: `Moderate / ${percentage}%`, variant: "info" };
  }

  return { label: `Low / ${percentage}%`, variant: "warning" };
}

export function getRiskStatus(riskLevel: string | null | undefined): ReportStatusValue {
  const label = formatRiskLevel(riskLevel);
  if (!riskLevel) {
    return { label, variant: "secondary" };
  }

  if (riskLevel.includes("high") || riskLevel.includes("critical")) {
    return { label, variant: "destructive" };
  }

  if (riskLevel.includes("medium") || riskLevel.includes("moderate")) {
    return { label, variant: "warning" };
  }

  if (riskLevel.includes("insufficient")) {
    return { label, variant: "secondary" };
  }

  return { label, variant: "success" };
}

export function getDataQualityStatus(score: number | null | undefined): ReportStatusValue {
  if (score == null) {
    return { label: "Unavailable", variant: "secondary" };
  }

  const percentage = Math.round(score * 100);
  if (percentage >= 80) {
    return { label: `${percentage}/100`, variant: "success" };
  }

  if (percentage >= 50) {
    return { label: `${percentage}/100`, variant: "warning" };
  }

  return { label: `${percentage}/100`, variant: "destructive" };
}

export function getDataStatusStatus(status: string | null | undefined): ReportStatusValue {
  if (!status) {
    return { label: "Unknown", variant: "secondary" };
  }

  if (status === "available") {
    return { label: "Available", variant: "success" };
  }

  if (status === "partial") {
    return { label: "Partial", variant: "warning" };
  }

  if (status === "missing") {
    return { label: "Missing", variant: "destructive" };
  }

  return { label: capitalize(status) ?? status, variant: "secondary" };
}

export function hasIncompleteData(finalReport: FinalReportView | null) {
  if (!finalReport) {
    return false;
  }

  return [
    finalReport.priceDataStatus,
    finalReport.newsDataStatus,
    finalReport.companyProfileStatus,
    finalReport.fundamentalsStatus,
  ].some((status) => status === "partial" || status === "missing");
}

export function formatHorizon(value: string | null | undefined) {
  if (!value) {
    return "Unknown";
  }

  const option = HORIZON_OPTIONS.find((item) => item.value === value);
  return option?.label ?? value;
}

export function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "-";
  }

  return `${Math.round(value * 100)}%`;
}

export function formatUsd(value: number | null | undefined, digits = 4) {
  if (value == null) {
    return "-";
  }

  return `$${value.toFixed(digits)}`;
}

export function formatPrice(value: number | null | undefined) {
  if (value == null) {
    return "-";
  }

  return `$${value.toFixed(2)}`;
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Unknown";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatAgentDuration(durationMs: number | null | undefined) {
  if (durationMs == null || durationMs <= 0) {
    return undefined;
  }

  if (durationMs < 1000) {
    return `${durationMs}ms`;
  }

  return `${(durationMs / 1000).toFixed(durationMs >= 10_000 ? 0 : 1)}s`;
}

export function buildAgentTimeline(report: ReportDetail | null) {
  if (!report) {
    return [];
  }

  const agentOrder = [
    "data_collector",
    "technical_agent",
    "news_sentiment_agent",
    "bull_case_agent",
    "bear_case_agent",
    "risk_review_agent",
    "thesis_agent",
    "report_writer_agent",
  ] as const;

  const outputsByAgent = new Map(
    report.agent_outputs.map((output) => [output.agent_name, output] as const),
  );
  const costByAgent = new Map(
    report.cost_breakdown.items.map((item) => [item.agent_name, item] as const),
  );

  return agentOrder
    .map((agentName) => {
      const output = outputsByAgent.get(agentName);
      const cost = costByAgent.get(agentName);
      if (!output && !cost) {
        return null;
      }

      return {
        id: agentName,
        name: formatAgentName(agentName),
        status: mapAgentStatus(output?.status),
        duration: formatAgentDuration(output?.duration_ms ?? cost?.duration_ms),
        provider: cost?.provider ?? output?.provider,
        model: cost?.model ?? output?.model,
        cost:
          output?.cost_usd != null || cost?.cost_usd != null
            ? formatUsd(output?.cost_usd ?? cost?.cost_usd ?? null)
            : undefined,
        inputTokens: output?.input_tokens ?? cost?.input_tokens ?? null,
        outputTokens: output?.output_tokens ?? cost?.output_tokens ?? null,
        warnings: dedupeStrings([
          ...(output?.warnings ?? []),
          ...(cost?.warnings ?? []),
          ...(cost?.parsing_errors ?? []),
        ]),
        errorMessage: output?.error_message ?? null,
      };
    })
    .filter((item): item is NonNullable<typeof item> => item != null);
}

function mapAgentStatus(status: string | undefined) {
  switch (status) {
    case "completed":
      return "completed" as const;
    case "partial":
      return "partial" as const;
    case "failed":
      return "failed" as const;
    case "running":
      return "running" as const;
    default:
      return "pending" as const;
  }
}

function getAgentOutput(report: ReportDetail | null, agentName: string) {
  return report?.agent_outputs.find((output) => output.agent_name === agentName) ?? null;
}

function getCollectorDataQuality(report: ReportDetail | null) {
  const collector = getObject(getAgentOutput(report, "data_collector")?.output_json);
  return getObject(collector?.data_quality);
}

function getTechnicalLevels(value: unknown): TechnicalLevelRecord[] {
  return getObjectArray(value)
    .map((item) => ({
      price: getNumber(item.price),
      reason: getString(item.reason),
      strength: getString(item.strength),
    }))
    .filter((item): item is TechnicalLevelRecord => item.price != null);
}

function splitDescriptor(value: string) {
  for (const separator of [": ", " - ", " | "]) {
    const index = value.indexOf(separator);
    if (index > 0) {
      return {
        title: value.slice(0, index).trim(),
        description: value.slice(index + separator.length).trim() || null,
      };
    }
  }

  return {
    title: value,
    description: null,
  };
}

function dedupeStrings(values: Array<string | null | undefined>) {
  const unique = new Set<string>();
  for (const value of values) {
    if (typeof value !== "string") {
      continue;
    }

    const trimmed = value.trim();
    if (!trimmed) {
      continue;
    }

    unique.add(trimmed);
  }

  return [...unique];
}

function capitalize(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getString(value: unknown) {
  return typeof value === "string" ? value : null;
}

function getNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
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
