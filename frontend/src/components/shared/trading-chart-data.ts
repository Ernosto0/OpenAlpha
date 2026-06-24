import type { ReportDetail } from "../../lib/api";

export type TradingBar = {
  timestamp: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
};

export function extractTradingHistory(report: ReportDetail | null): TradingBar[] {
  if (!report) {
    return [];
  }

  const collector = report.agent_outputs.find((output) => output.agent_name === "data_collector");
  const marketData = getObject(collector?.output_json?.market_data);
  const priceHistory = getObjectArray(marketData?.price_history);

  return priceHistory
    .map((bar) => ({
      timestamp: typeof bar.timestamp === "string" ? bar.timestamp : "",
      open: getNumber(bar.open),
      high: getNumber(bar.high),
      low: getNumber(bar.low),
      close: getNumber(bar.close) ?? 0,
      volume: getNumber(bar.volume),
    }))
    .filter((bar) => bar.timestamp && Number.isFinite(bar.close));
}

function getObject(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function getObjectArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
    : [];
}

function getNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
