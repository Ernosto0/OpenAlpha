import { Save, Lock, Database, Cpu, HardDrive } from "lucide-react";
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
import { StatusBadge } from "../components/shared/status-badges";

export function SettingsPage() {
  const [saved, setSaved] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  return (
    <>
      <PageHeader
        eyebrow="Settings"
        title="Environment Configuration"
        description="Manage local-first trust, provider credentials, and system parameters."
      />

      <form className="grid gap-6 lg:grid-cols-2" onSubmit={handleSubmit}>
        
        {/* API Keys / Secrets */}
        <Card className="bg-card shadow-panel border-border">
          <CardHeader className="border-b border-border pb-4 bg-muted/10">
            <div className="flex justify-between items-center">
              <CardTitle className="flex items-center gap-2 text-base">
                <Lock className="h-4 w-4" />
                API Keys & Secrets
              </CardTitle>
            </div>
            <CardDescription>Credentials are encrypted and stored locally in your SQLite DB.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="openai-key">OpenAI API Key</Label>
                <StatusBadge status="Connected" variant="success" />
              </div>
              <Input
                id="openai-key"
                name="openai-key"
                defaultValue="sk-..."
                type="password"
                className="font-mono"
              />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="anthropic-key">Anthropic API Key</Label>
                <StatusBadge status="Missing key" variant="warning" />
              </div>
              <Input
                id="anthropic-key"
                name="anthropic-key"
                placeholder="sk-ant-..."
                type="password"
                className="font-mono"
              />
            </div>
          </CardContent>
        </Card>

        {/* Model Defaults */}
        <Card className="bg-card shadow-panel border-border">
          <CardHeader className="border-b border-border pb-4 bg-muted/10">
            <CardTitle className="flex items-center gap-2 text-base">
              <Cpu className="h-4 w-4" />
              LLM Providers & Defaults
            </CardTitle>
            <CardDescription>Configure routing for analysis and reporting agents.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="default-provider">Default Provider</Label>
                <StatusBadge status="Active" variant="success" />
              </div>
              <Select id="default-provider" name="default-provider" defaultValue="openai">
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="local">Local (Ollama)</option>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="default-model">Default Model</Label>
              </div>
              <Input id="default-model" name="default-model" defaultValue="gpt-4o" className="font-mono" />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="local-url">Local API URL (Ollama/Llama.cpp)</Label>
                <StatusBadge status="Untested" variant="secondary" />
              </div>
              <Input id="local-url" name="local-url" defaultValue="http://localhost:11434" className="font-mono" />
            </div>
          </CardContent>
        </Card>

        {/* Market Data Providers */}
        <Card className="bg-card shadow-panel border-border">
          <CardHeader className="border-b border-border pb-4 bg-muted/10">
            <CardTitle className="flex items-center gap-2 text-base">
              <Database className="h-4 w-4" />
              Market Data Providers
            </CardTitle>
            <CardDescription>Configure data sources for fundamental and pricing data.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="fmp-key">Financial Modeling Prep</Label>
                <StatusBadge status="Connected" variant="success" />
              </div>
              <Input
                id="fmp-key"
                name="fmp-key"
                defaultValue="xxxxx"
                type="password"
                className="font-mono"
              />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label htmlFor="yfinance">Yahoo Finance (Local fallback)</Label>
                <StatusBadge status="Local" variant="info" />
              </div>
              <div className="text-sm text-muted-foreground mt-1">Used automatically if primary data provider fails. No key required.</div>
            </div>
          </CardContent>
        </Card>

        {/* Local Config & Cache */}
        <Card className="bg-card shadow-panel border-border">
          <CardHeader className="border-b border-border pb-4 bg-muted/10">
            <CardTitle className="flex items-center gap-2 text-base">
              <HardDrive className="h-4 w-4" />
              Local Storage & Cache
            </CardTitle>
            <CardDescription>Manage SQLite database and report caching.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-2">
              <Label>SQLite DB Path</Label>
              <div className="px-3 py-2 bg-muted/50 rounded-md border border-border text-sm font-mono text-muted-foreground break-all">
                ./openalpha.db
              </div>
            </div>
            <div className="space-y-2">
              <Label>Data Cache</Label>
              <div className="flex items-center gap-3">
                <Select defaultValue="7d">
                  <option value="1d">Retain 1 Day</option>
                  <option value="7d">Retain 7 Days</option>
                  <option value="30d">Retain 30 Days</option>
                  <option value="forever">Keep Forever</option>
                </Select>
                <Button type="button" variant="secondary">Clear Cache</Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Submit Actions */}
        <div className="lg:col-span-2 flex items-center justify-end gap-4 border-t border-border pt-6">
          {saved && (
            <span className="text-sm font-mono text-success">
              [SYSTEM] Configuration updated successfully.
            </span>
          )}
          <Button type="submit" className="font-semibold font-mono bg-primary text-primary-foreground">
            <Save className="h-4 w-4 mr-2" aria-hidden="true" />
            Apply Settings
          </Button>
        </div>

      </form>
    </>
  );
}
