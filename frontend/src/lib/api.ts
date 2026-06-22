export type HealthResponse = {
  status: "ok";
  service: string;
  version: string;
  timestamp: string;
};

export type AppInfoResponse = {
  name: string;
  positioning: string;
  disclaimer: string;
  health_url: string;
};

export type ProviderStatus =
  | "configured"
  | "missing"
  | "tested"
  | "failed"
  | "untested";

export type RuntimeProvider = "openai" | "claude" | "gemini" | "local";

export type RemoteProviderSettings = {
  api_key_configured: boolean;
  api_key_masked: string | null;
  status: ProviderStatus;
  last_test_message: string | null;
  last_tested_at: string | null;
};

export type LocalSettings = {
  base_url: string;
  model: string;
  status: ProviderStatus;
  last_test_message: string | null;
  last_tested_at: string | null;
};

export type ConfiguredProviderSummary = {
  provider: RuntimeProvider;
  label: string;
  status: ProviderStatus;
  model: string | null;
};

export type AppSettings = {
  default_provider: RuntimeProvider;
  default_model: string;
  providers: {
    openai: RemoteProviderSettings;
    claude: RemoteProviderSettings;
    gemini: RemoteProviderSettings;
    local: LocalSettings;
  };
  configured_providers: ConfiguredProviderSummary[];
};

export type AppSettingsUpdate = {
  default_provider: RuntimeProvider;
  default_model: string;
  openai_api_key: string | null;
  anthropic_api_key: string | null;
  gemini_api_key: string | null;
  ollama_base_url: string;
  ollama_model: string;
};

export type ProviderTestResult = {
  provider: RuntimeProvider;
  success: boolean;
  status: ProviderStatus;
  message: string;
  tested_at: string;
};

export type AnalysisRequest = {
  symbol: string;
  market: "US" | "GLOBAL";
  horizon: "1w" | "1m" | "3m" | "6m" | "1y";
  depth: "quick" | "standard" | "deep";
  language: "en" | "tr";
  llm_provider: string;
  llm_model: string;
  custom_question: string | null;
};

export type AnalysisRunAcceptedResponse = {
  run_id: string;
  status: string;
};

export type AnalysisEvent = {
  type:
    | "analysis_started"
    | "agent_started"
    | "agent_finished"
    | "agent_failed"
    | "analysis_completed"
    | "analysis_failed";
  run_id: string;
  timestamp: string;
  agent_name: string | null;
  status: string | null;
  message: string | null;
  error_message: string | null;
};

export type AnalysisAgentOutputResponse = {
  agent_name: string;
  status: string;
  output_json: Record<string, unknown> | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
};

export type AnalysisRunDetailResponse = {
  run_id: string;
  status: string;
  symbol: string;
  market: string;
  horizon: string;
  depth: string;
  language: string;
  total_cost_usd: number;
  data_quality_score: number | null;
  finished_at: string | null;
  error_message: string | null;
  agent_outputs: AnalysisAgentOutputResponse[];
  report_id: string | null;
};

export type AnalysisRunEventsResponse = {
  run_id: string;
  events: AnalysisEvent[];
};

export type ReportSummary = {
  id: string;
  symbol: string;
  horizon: string;
  overall_view: string;
  confidence: number | null;
  risk_level: string | null;
  created_at: string;
};

export type ReportCostItem = {
  agent_name: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  created_at: string;
};

export type ReportSourceItem = {
  name: string;
  type: string;
  provider: string;
  url: string | null;
  used_for: string;
};

export type ReportDataQuality = {
  data_quality_score: number | null;
  price_data_status: string;
  news_data_status: string;
  company_profile_status: string;
  missing_data: string[];
  providers: string[];
  warnings: string[];
};

export type ReportDetail = ReportSummary & {
  run_id: string;
  status: string;
  market: string;
  final_report: Record<string, unknown>;
  agent_outputs: AnalysisAgentOutputResponse[];
  cost_breakdown: {
    total_cost_usd: number;
    items: ReportCostItem[];
  };
  data_quality: ReportDataQuality | null;
  sources: ReportSourceItem[];
  warnings: string[];
};

export type PerformanceSummary = {
  direction_correctness: number | null;
  relative_performance: number | null;
  evaluated_reports: number;
  total_reports: number;
  average_hold_days: number | null;
};

export type PerformanceBreakdownItem = {
  label: string;
  correctness_rate: number | null;
  evaluated_count: number;
  average_return: number | null;
  average_alpha: number | null;
};

export type PerformanceEvaluationItem = {
  report_id: string;
  symbol: string;
  market: string;
  horizon: string;
  overall_view: string;
  model: string;
  report_created_at: string;
  evaluation_status: "interim" | "matured";
  days_elapsed: number;
  target_days: number;
  entry_price: number | null;
  latest_price: number | null;
  realized_return: number | null;
  benchmark_symbol: string | null;
  benchmark_return: number | null;
  alpha: number | null;
  direction_result: "correct" | "incorrect" | "not_scored";
};

export type PerformanceResponse = {
  summary: PerformanceSummary;
  by_model: PerformanceBreakdownItem[];
  by_horizon: PerformanceBreakdownItem[];
  recent_evaluations: PerformanceEvaluationItem[];
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

const WS_BASE_URL = API_BASE_URL.replace(/^http/i, "ws");

class ApiError extends Error {
  status: number;
  detail: string | null;

  constructor(message: string, status: number, detail: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let detail: string | null = null;
    try {
      const errorBody = (await response.json()) as { detail?: unknown };
      if (typeof errorBody.detail === "string" && errorBody.detail.trim()) {
        detail = errorBody.detail.trim();
      }
    } catch {
      detail = null;
    }
    throw new ApiError(
      detail ?? `Request failed with status ${response.status}`,
      response.status,
      detail,
    );
  }

  return response.json() as Promise<T>;
}

export const api = {
  getAppInfo: () => request<AppInfoResponse>("/"),
  getHealth: () => request<HealthResponse>("/api/health"),
  getSettings: () => request<AppSettings>("/api/settings"),
  saveSettings: (settings: AppSettingsUpdate) =>
    request<AppSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  testProvider: (provider: RuntimeProvider) =>
    request<ProviderTestResult>("/api/providers/llm/test", {
      method: "POST",
      body: JSON.stringify({ provider }),
    }),
  runAnalysis: (payload: AnalysisRequest) =>
    request<AnalysisRunAcceptedResponse>("/api/analysis/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAnalysisRun: (runId: string) =>
    request<AnalysisRunDetailResponse>(`/api/analysis/${runId}`),
  getAnalysisEvents: (runId: string) =>
    request<AnalysisRunEventsResponse>(`/api/analysis/${runId}/events`),
  createAnalysisRunWebSocket: (runId: string) =>
    new WebSocket(`${WS_BASE_URL}/ws/analysis/${runId}`),
  listReports: () => request<ReportSummary[]>("/api/reports"),
  getReport: (id: string) => request<ReportDetail>(`/api/reports/${id}`),
  getPerformance: () => request<PerformanceResponse>("/api/performance"),
};

export { ApiError };
