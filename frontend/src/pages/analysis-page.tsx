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
import { AgentTimeline, type AgentRun } from "../components/shared/agent-timeline";

const mockAgents: AgentRun[] = [
  { id: "1", name: "Data Collector", status: "completed", duration: "1.2s" },
  { id: "2", name: "Technical Research", status: "completed", duration: "4.5s", provider: "OpenAI", model: "gpt-4o", cost: "$0.02" },
  { id: "3", name: "News Sentiment", status: "completed", duration: "3.1s", provider: "OpenAI", model: "gpt-4o", cost: "$0.01" },
  { id: "4", name: "Bull Case", status: "completed", duration: "8.2s", provider: "Anthropic", model: "claude-3.5-sonnet", cost: "$0.04" },
  { id: "5", name: "Bear Case", status: "running", provider: "Anthropic", model: "claude-3.5-sonnet" },
  { id: "6", name: "Risk Review", status: "pending" },
  { id: "7", name: "Thesis", status: "pending" },
  { id: "8", name: "Report Writer", status: "pending" },
];

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
        title="Run Analysis"
        description="Configure structured parameters for a comprehensive equity research pass."
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
        <Card className="bg-card shadow-panel">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle>Research Parameters</CardTitle>
            <CardDescription>Define the scope and configure LLM routing for this run.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form className="grid gap-6" onSubmit={handleSubmit}>
              <div className="grid gap-6 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="symbol">Symbol</Label>
                  <Input id="symbol" name="symbol" placeholder="AAPL" required className="font-mono" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="market">Market</Label>
                  <Select id="market" name="market" defaultValue="us">
                    <option value="us">US Equities (NYSE/NASDAQ)</option>
                    <option value="crypto">Crypto</option>
                    <option value="eu">European Equities</option>
                  </Select>
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="horizon">Time Horizon</Label>
                  <Select id="horizon" name="horizon" defaultValue="medium">
                    <option value="short">Short Term (1-3 Mo)</option>
                    <option value="medium">Medium Term (6-12 Mo)</option>
                    <option value="long">Long Term (1-3 Yr)</option>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="depth">Analysis Depth</Label>
                  <Select id="depth" name="depth" defaultValue="standard">
                    <option value="quick">Quick Summary (1 page)</option>
                    <option value="standard">Standard Report (3-5 pages)</option>
                    <option value="deep">Deep Dive (10+ pages)</option>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="provider">LLM Provider</Label>
                  <Select id="provider" name="provider" defaultValue="openai">
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="local">Local (Ollama)</option>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="model">Model</Label>
                  <Select id="model" name="model" defaultValue="gpt-4o">
                    <option value="gpt-4o">gpt-4o</option>
                    <option value="claude-3-5-sonnet">claude-3.5-sonnet</option>
                    <option value="llama3">llama3</option>
                  </Select>
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="language">Language</Label>
                  <Select id="language" name="language" defaultValue="en">
                    <option value="en">English</option>
                    <option value="es">Spanish</option>
                    <option value="fr">French</option>
                  </Select>
                </div>
              </div>

              <div className="grid gap-2 mt-2">
                <Label htmlFor="focus">Optional Research Focus (e.g. "Focus on AI hardware strategy")</Label>
                <Input id="focus" name="focus" placeholder="Enter specific research direction..." />
              </div>

              <div className="pt-2">
                <Button type="submit" className="w-full sm:w-auto font-semibold font-mono bg-primary text-primary-foreground">
                  <PlayCircle className="h-4 w-4 mr-2" aria-hidden="true" />
                  Run Research Agents
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="bg-card shadow-panel">
            <CardHeader className="border-b border-border pb-4">
              <CardTitle>Execution Trace</CardTitle>
              <CardDescription>Real-time agent progression.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {queuedSymbol ? (
                <AgentTimeline agents={mockAgents} />
              ) : (
                <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-sm text-muted-foreground">
                  Waiting for task...
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
