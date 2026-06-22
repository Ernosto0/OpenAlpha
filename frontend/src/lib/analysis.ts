export const MARKET_OPTIONS = [
  { value: "US", label: "US Equities" },
  { value: "GLOBAL", label: "Global Equities" },
] as const;

export const HORIZON_OPTIONS = [
  { value: "1w", label: "1 Week" },
  { value: "1m", label: "1 Month" },
  { value: "3m", label: "3 Months" },
  { value: "6m", label: "6 Months" },
  { value: "1y", label: "1 Year" },
] as const;

export const DEPTH_OPTIONS = [
  { value: "quick", label: "Quick Summary" },
  { value: "standard", label: "Standard Report" },
  { value: "deep", label: "Deep Dive" },
] as const;

export const PROVIDER_MODEL_OPTIONS = {
  openai: [
    { value: "gpt-4.1-mini", label: "gpt-4.1-mini" },
    { value: "gpt-4.1", label: "gpt-4.1" },
    { value: "gpt-4o", label: "gpt-4o" },
  ],
  claude: [
    { value: "claude-3-5-sonnet-latest", label: "claude-3-5-sonnet-latest" },
    { value: "claude-3-7-sonnet-latest", label: "claude-3-7-sonnet-latest" },
    { value: "claude-3-5-haiku-latest", label: "claude-3-5-haiku-latest" },
  ],
  gemini: [
    { value: "gemini-2.5-pro", label: "gemini-2.5-pro" },
    { value: "gemini-2.5-flash", label: "gemini-2.5-flash" },
  ],
  local: [
    { value: "llama3", label: "llama3" },
  ],
} as const;

export type AnalysisProvider = keyof typeof PROVIDER_MODEL_OPTIONS;

export const DEFAULT_PROVIDER: AnalysisProvider = "openai";
export const DEFAULT_MODEL =
  PROVIDER_MODEL_OPTIONS[DEFAULT_PROVIDER][0].value;

export function getModelsForProvider(provider: string) {
  return (
    PROVIDER_MODEL_OPTIONS[
      provider as keyof typeof PROVIDER_MODEL_OPTIONS
    ] ?? PROVIDER_MODEL_OPTIONS[DEFAULT_PROVIDER]
  );
}

export function getModelOptionsForSelection(provider: string, currentModel: string) {
  const knownOptions = getModelsForProvider(provider);
  if (knownOptions.some((option) => option.value === currentModel)) {
    return knownOptions;
  }
  return [
    { value: currentModel, label: `${currentModel} (saved)` },
    ...knownOptions,
  ];
}

export function getProviderLabel(provider: string) {
  switch (provider) {
    case "openai":
      return "OpenAI";
    case "claude":
      return "Claude";
    case "gemini":
      return "Gemini";
    case "local":
      return "Ollama";
    default:
      return provider;
  }
}

export function formatOverallView(view: string) {
  return view
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatRiskLevel(level: string | null | undefined) {
  if (!level) {
    return "Unknown";
  }

  return level
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function toRiskBadgeLevel(level: string | null | undefined) {
  const formatted = formatRiskLevel(level);

  if (formatted.includes("High") || formatted.includes("Critical")) {
    return "High" as const;
  }

  if (formatted.includes("Medium") || formatted.includes("Moderate")) {
    return "Medium" as const;
  }

  return "Low" as const;
}

export function formatAgentName(name: string) {
  const labels: Record<string, string> = {
    data_collector: "Data Collector",
    technical_agent: "Technical Agent",
    fundamental_agent: "Fundamental Agent",
    news_sentiment_agent: "News Agent",
    bull_case_agent: "Bull Case Agent",
    bear_case_agent: "Bear Case Agent",
    risk_review_agent: "Risk Review Agent",
    thesis_agent: "Thesis Agent",
    critic_agent: "Critic Agent",
    report_writer_agent: "Report Writer",
  };

  return labels[name] ?? name;
}
