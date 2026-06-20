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

export type ProviderSettings = {
  provider: "openai" | "anthropic" | "local";
  model: string;
  apiKeyConfigured: boolean;
};

export type AnalysisRequest = {
  symbol: string;
  horizon: "short" | "medium" | "long";
  includeRisks: boolean;
};

export type AnalysisResponse = {
  reportId: string;
  status: "queued" | "running" | "complete" | "failed";
};

export type ReportSummary = {
  id: string;
  symbol: string;
  title: string;
  status: "draft" | "complete" | "failed";
  createdAt: string;
};

export type ReportDetail = ReportSummary & {
  thesis: string;
  risks: string[];
  sources: string[];
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
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
    throw new ApiError(`Request failed with status ${response.status}`, response.status);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getAppInfo: () => request<AppInfoResponse>("/"),
  getHealth: () => request<HealthResponse>("/api/health"),
  getProviderSettings: () =>
    request<ProviderSettings>("/api/settings/provider"),
  saveProviderSettings: (settings: ProviderSettings) =>
    request<ProviderSettings>("/api/settings/provider", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  runAnalysis: (payload: AnalysisRequest) =>
    request<AnalysisResponse>("/api/analysis", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listReports: () => request<ReportSummary[]>("/api/reports"),
  getReport: (id: string) => request<ReportDetail>(`/api/reports/${id}`),
};
