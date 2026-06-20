import type { ReportDetail, ReportSummary } from "../lib/api";

export const reportHistory: ReportSummary[] = [
  {
    id: "rpt-aapl-2026-06",
    symbol: "AAPL",
    title: "Apple cash flow and device cycle review",
    status: "complete",
    createdAt: "2026-06-20T21:22:00Z",
  },
  {
    id: "rpt-nvda-2026-06",
    symbol: "NVDA",
    title: "NVIDIA data center margin sensitivity",
    status: "draft",
    createdAt: "2026-06-19T14:05:00Z",
  },
  {
    id: "rpt-msft-2026-06",
    symbol: "MSFT",
    title: "Microsoft cloud growth and capital intensity",
    status: "complete",
    createdAt: "2026-06-18T10:41:00Z",
  },
];

export const reportDetails: Record<string, ReportDetail> = {
  "rpt-aapl-2026-06": {
    ...reportHistory[0],
    thesis:
      "Apple remains highly cash generative, but near-term upside depends on stronger services mix and a clearer device refresh catalyst.",
    risks: [
      "Hardware replacement cycles may stay elongated.",
      "Regulatory pressure could limit services economics.",
      "Currency and supply chain swings can pressure margins.",
    ],
    sources: ["10-K", "latest earnings call", "segment revenue trend"],
  },
  "rpt-nvda-2026-06": {
    ...reportHistory[1],
    thesis:
      "Demand remains broad, while the main research question is whether customer concentration and supply mix change margin durability.",
    risks: [
      "Hyperscaler spending could normalize faster than expected.",
      "Export controls may constrain some revenue pools.",
      "Competition in accelerator silicon may compress multiples.",
    ],
    sources: ["10-Q", "data center revenue trend", "capex commentary"],
  },
  "rpt-msft-2026-06": {
    ...reportHistory[2],
    thesis:
      "Microsoft's AI infrastructure spending is defensible if Azure share gains and application attach rates continue to compound.",
    risks: [
      "AI capex may outpace monetization windows.",
      "Enterprise budget cycles may slow seat expansion.",
      "Cloud competition remains intense on price and platform depth.",
    ],
    sources: ["10-K", "Azure disclosures", "commercial bookings trend"],
  },
};
