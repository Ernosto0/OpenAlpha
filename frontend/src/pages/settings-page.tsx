import { LoaderCircle, Lock, Save, Server, TestTube2 } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { PageHeader } from "../components/page-header";
import { StatusBadge } from "../components/shared/status-badges";
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
import {
  getModelOptionsForSelection,
  getModelsForProvider,
  getProviderLabel,
  type AnalysisProvider,
} from "../lib/analysis";
import {
  api,
  type AppSettingsUpdate,
  type OllamaModelInfo,
  type ProviderStatus,
  type RuntimeProvider,
} from "../lib/api";
import { useAppSettings } from "../lib/settings-context";

type SettingsFormState = {
  openaiApiKey: string;
  anthropicApiKey: string;
  geminiApiKey: string;
  ollamaBaseUrl: string;
  ollamaModel: string;
  defaultProvider: RuntimeProvider;
  defaultModel: string;
};

const EMPTY_FORM: SettingsFormState = {
  openaiApiKey: "",
  anthropicApiKey: "",
  geminiApiKey: "",
  ollamaBaseUrl: "http://localhost:11434",
  ollamaModel: "llama3",
  defaultProvider: "openai",
  defaultModel: "gpt-4.1-mini",
};

export function SettingsPage() {
  const { settings, isLoading, error, applySettings, refresh } = useAppSettings();
  const [formState, setFormState] = useState<SettingsFormState>(EMPTY_FORM);
  const [saveState, setSaveState] = useState<{
    status: "idle" | "saving" | "saved" | "error";
    message: string | null;
  }>({ status: "idle", message: null });
  const [testingProvider, setTestingProvider] = useState<RuntimeProvider | null>(null);
  const [ollamaModels, setOllamaModels] = useState<OllamaModelInfo[]>([]);

  useEffect(() => {
    if (!settings) {
      return;
    }

    setFormState({
      openaiApiKey: "",
      anthropicApiKey: "",
      geminiApiKey: "",
      ollamaBaseUrl: settings.providers.ollama.base_url,
      ollamaModel: settings.providers.ollama.model,
      defaultProvider: settings.default_provider,
      defaultModel: settings.default_model,
    });
  }, [settings]);

  useEffect(() => {
    const baseUrl = formState.ollamaBaseUrl.trim();
    if (!baseUrl) {
      setOllamaModels([]);
      return;
    }

    let active = true;
    api
      .listOllamaModels(baseUrl)
      .then((models) => {
        if (active) {
          setOllamaModels(models);
        }
      })
      .catch(() => {
        if (active) {
          setOllamaModels([]);
        }
      });

    return () => {
      active = false;
    };
  }, [formState.ollamaBaseUrl]);

  const modelOptions = useMemo(
    () => getModelOptionsForSelection(formState.defaultProvider, formState.defaultModel),
    [formState.defaultModel, formState.defaultProvider],
  );

  function updateField<K extends keyof SettingsFormState>(
    field: K,
    value: SettingsFormState[K],
  ) {
    setFormState((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleProviderChange(provider: RuntimeProvider) {
    const nextDefaultModel =
      provider === "ollama"
        ? formState.ollamaModel
        : getModelsForProvider(provider)[0]?.value ?? "gpt-4.1-mini";

    setFormState((current) => ({
      ...current,
      defaultProvider: provider,
      defaultModel: nextDefaultModel,
    }));
  }

  const ollamaModelOptions = useMemo(() => {
    const knownOptions = ollamaModels.map((model) => ({
      value: model.id,
      label: model.id,
    }));
    if (knownOptions.some((option) => option.value === formState.ollamaModel)) {
      return knownOptions;
    }
    if (!formState.ollamaModel.trim()) {
      return knownOptions;
    }
    return [
      { value: formState.ollamaModel, label: `${formState.ollamaModel} (saved)` },
      ...knownOptions,
    ];
  }, [formState.ollamaModel, ollamaModels]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveState({ status: "saving", message: null });

    const payload: AppSettingsUpdate = {
      default_provider: formState.defaultProvider,
      default_model:
        formState.defaultProvider === "ollama"
          ? formState.ollamaModel.trim()
          : formState.defaultModel.trim(),
      openai_api_key: formState.openaiApiKey.trim() || null,
      anthropic_api_key: formState.anthropicApiKey.trim() || null,
      gemini_api_key: formState.geminiApiKey.trim() || null,
      ollama_base_url: formState.ollamaBaseUrl.trim(),
      ollama_model: formState.ollamaModel.trim(),
    };

    try {
      const response = await api.saveSettings(payload);
      applySettings(response);
      setFormState((current) => ({
        ...current,
        openaiApiKey: "",
        anthropicApiKey: "",
        geminiApiKey: "",
        defaultModel: response.default_model,
      }));
      setSaveState({
        status: "saved",
        message: "Configuration updated successfully.",
      });
    } catch {
      setSaveState({
        status: "error",
        message: "Unable to save settings.",
      });
    }
  }

  async function handleProviderTest(provider: RuntimeProvider) {
    setTestingProvider(provider);
    setSaveState({ status: "idle", message: null });
    try {
      await api.testProvider({
        provider,
        base_url: provider === "ollama" ? formState.ollamaBaseUrl.trim() : undefined,
        model: provider === "ollama" ? formState.ollamaModel.trim() : undefined,
      });
      await refresh();
    } catch {
      setSaveState({
        status: "error",
        message: `Unable to test ${getProviderLabel(provider)}.`,
      });
    } finally {
      setTestingProvider(null);
    }
  }

  const openaiSettings = settings?.providers.openai;
  const claudeSettings = settings?.providers.claude;
  const geminiSettings = settings?.providers.gemini;
  const ollamaSettings = settings?.providers.ollama;

  return (
    <>
      <PageHeader
        eyebrow="Settings"
        title="Environment Configuration"
        description="Manage local provider credentials, runtime defaults, and connectivity state."
      />

      <form className="grid gap-6 lg:grid-cols-2" onSubmit={handleSubmit}>
        <Card className="border-border bg-card shadow-panel">
          <CardHeader className="border-b border-border bg-muted/10 pb-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <Lock className="h-4 w-4" />
              Provider Credentials
            </CardTitle>
            <CardDescription>Credentials are persisted locally through the backend.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5 pt-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="openai-key">OpenAI API Key</Label>
                <StatusBadge
                  status={statusLabel(openaiSettings?.status ?? "missing")}
                  variant={statusVariant(openaiSettings?.status ?? "missing")}
                />
              </div>
              <Input
                id="openai-key"
                name="openai-key"
                placeholder={
                  openaiSettings?.api_key_masked
                    ? `Saved: ${openaiSettings.api_key_masked}`
                    : "sk-..."
                }
                type="password"
                className="font-mono"
                value={formState.openaiApiKey}
                onChange={(event) => updateField("openaiApiKey", event.target.value)}
              />
              <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                <span>
                  {openaiSettings?.api_key_configured
                    ? `Stored locally as ${openaiSettings.api_key_masked}. Leave blank to keep it.`
                    : "No OpenAI key stored yet."}
                </span>
                <Button
                  type="button"
                  variant="secondary"
                  className="font-mono"
                  disabled={testingProvider === "openai"}
                  onClick={() => void handleProviderTest("openai")}
                >
                  {testingProvider === "openai" ? (
                    <LoaderCircle className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <TestTube2 className="mr-2 h-4 w-4" aria-hidden="true" />
                  )}
                  Test OpenAI
                </Button>
              </div>
              {openaiSettings?.last_test_message ? (
                <p className="text-xs text-muted-foreground">{openaiSettings.last_test_message}</p>
              ) : null}
            </div>

            <div className="space-y-2 border-t border-border pt-5">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="claude-key">Claude API Key</Label>
                <StatusBadge
                  status={statusLabel(claudeSettings?.status ?? "missing")}
                  variant={statusVariant(claudeSettings?.status ?? "missing")}
                />
              </div>
              <Input
                id="claude-key"
                name="claude-key"
                placeholder={
                  claudeSettings?.api_key_masked
                    ? `Saved: ${claudeSettings.api_key_masked}`
                    : "sk-ant-..."
                }
                type="password"
                className="font-mono"
                value={formState.anthropicApiKey}
                onChange={(event) => updateField("anthropicApiKey", event.target.value)}
              />
              <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                <span>
                  {claudeSettings?.api_key_configured
                    ? `Stored locally as ${claudeSettings.api_key_masked}. Leave blank to keep it.`
                    : "No Claude key stored yet."}
                </span>
                <Button
                  type="button"
                  variant="secondary"
                  className="font-mono"
                  disabled={testingProvider === "claude"}
                  onClick={() => void handleProviderTest("claude")}
                >
                  {testingProvider === "claude" ? (
                    <LoaderCircle className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <TestTube2 className="mr-2 h-4 w-4" aria-hidden="true" />
                  )}
                  Test Claude
                </Button>
              </div>
              {claudeSettings?.last_test_message ? (
                <p className="text-xs text-muted-foreground">{claudeSettings.last_test_message}</p>
              ) : null}
            </div>

            <div className="space-y-2 border-t border-border pt-5">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="gemini-key">Gemini API Key</Label>
                <StatusBadge
                  status={statusLabel(geminiSettings?.status ?? "missing")}
                  variant={statusVariant(geminiSettings?.status ?? "missing")}
                />
              </div>
              <Input
                id="gemini-key"
                name="gemini-key"
                placeholder={
                  geminiSettings?.api_key_masked
                    ? `Saved: ${geminiSettings.api_key_masked}`
                    : "AIza..."
                }
                type="password"
                className="font-mono"
                value={formState.geminiApiKey}
                onChange={(event) => updateField("geminiApiKey", event.target.value)}
              />
              <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                <span>
                  {geminiSettings?.api_key_configured
                    ? `Stored locally as ${geminiSettings.api_key_masked}. Leave blank to keep it.`
                    : "No Gemini key stored yet."}
                </span>
                <Button
                  type="button"
                  variant="secondary"
                  className="font-mono"
                  disabled={testingProvider === "gemini"}
                  onClick={() => void handleProviderTest("gemini")}
                >
                  {testingProvider === "gemini" ? (
                    <LoaderCircle className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <TestTube2 className="mr-2 h-4 w-4" aria-hidden="true" />
                  )}
                  Test Gemini
                </Button>
              </div>
              {geminiSettings?.last_test_message ? (
                <p className="text-xs text-muted-foreground">{geminiSettings.last_test_message}</p>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-panel">
          <CardHeader className="border-b border-border bg-muted/10 pb-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <Server className="h-4 w-4" />
              Ollama Runtime
            </CardTitle>
            <CardDescription>Base URL and default model for the local provider path.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5 pt-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="ollama-base-url">Ollama Base URL</Label>
                <StatusBadge
                  status={statusLabel(ollamaSettings?.status ?? "untested")}
                  variant={statusVariant(ollamaSettings?.status ?? "untested")}
                />
              </div>
              <Input
                id="ollama-base-url"
                name="ollama-base-url"
                className="font-mono"
                value={formState.ollamaBaseUrl}
                onChange={(event) => updateField("ollamaBaseUrl", event.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="ollama-model">Ollama Model</Label>
              <Select
                id="ollama-model"
                name="ollama-model"
                value={formState.ollamaModel}
                onChange={(event) => {
                  const nextModel = event.target.value;
                  setFormState((current) => ({
                    ...current,
                    ollamaModel: nextModel,
                    defaultModel:
                      current.defaultProvider === "ollama" ? nextModel : current.defaultModel,
                  }));
                }}
              >
                {ollamaModelOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
              <span>
                {ollamaSettings?.last_test_message ??
                  "Live installed models are fetched from the configured Ollama runtime."}
              </span>
              <Button
                type="button"
                variant="secondary"
                className="font-mono"
                disabled={testingProvider === "ollama"}
                onClick={() => void handleProviderTest("ollama")}
              >
                {testingProvider === "ollama" ? (
                  <LoaderCircle className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <TestTube2 className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Test Ollama
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-panel">
          <CardHeader className="border-b border-border bg-muted/10 pb-4">
            <CardTitle className="text-base">Default Runtime</CardTitle>
            <CardDescription>These defaults are used across the dashboard and analysis forms.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-6">
            <div className="space-y-2">
              <Label htmlFor="default-provider">Default Provider</Label>
              <Select
                id="default-provider"
                name="default-provider"
                value={formState.defaultProvider}
                onChange={(event) => handleProviderChange(event.target.value as AnalysisProvider)}
              >
                <option value="openai">OpenAI</option>
                <option value="claude">Claude</option>
                <option value="gemini">Gemini</option>
                <option value="ollama">Ollama</option>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="default-model">Default Model</Label>
              {formState.defaultProvider === "ollama" ? (
                <Select
                  id="default-model"
                  name="default-model"
                  value={formState.ollamaModel}
                  onChange={(event) => {
                    const nextModel = event.target.value;
                    setFormState((current) => ({
                      ...current,
                      ollamaModel: nextModel,
                      defaultModel: nextModel,
                    }));
                  }}
                >
                  {ollamaModelOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              ) : (
                <Select
                  id="default-model"
                  name="default-model"
                  value={formState.defaultModel}
                  onChange={(event) => updateField("defaultModel", event.target.value)}
                >
                  {modelOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-panel">
          <CardHeader className="border-b border-border bg-muted/10 pb-4">
            <CardTitle className="text-base">Configured Providers</CardTitle>
            <CardDescription>Backend-visible provider configuration and last known state.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-6">
            {settings?.configured_providers.length ? (
              settings.configured_providers.map((provider) => (
                <div
                  key={provider.provider}
                  className="flex items-center justify-between gap-4 rounded-md border border-border bg-muted/20 px-3 py-3"
                >
                  <div>
                    <p className="font-medium">{provider.label}</p>
                    <p className="text-sm text-muted-foreground">
                      {provider.model ?? "Credential configured"}
                    </p>
                  </div>
                  <StatusBadge
                    status={statusLabel(provider.status)}
                    variant={statusVariant(provider.status)}
                  />
                </div>
              ))
            ) : (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                No providers configured yet.
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex items-center justify-between gap-4 border-t border-border pt-6 lg:col-span-2">
          <div className="text-sm">
            {isLoading ? (
              <span className="text-muted-foreground">Loading settings...</span>
            ) : saveState.message ? (
              <span
                className={
                  saveState.status === "error" ? "text-destructive" : "text-success"
                }
              >
                {saveState.message}
              </span>
            ) : error ? (
              <span className="text-destructive">{error}</span>
            ) : null}
          </div>

          <Button
            type="submit"
            className="bg-primary font-mono font-semibold text-primary-foreground"
            disabled={isLoading || saveState.status === "saving"}
          >
            {saveState.status === "saving" ? (
              <LoaderCircle className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Save className="mr-2 h-4 w-4" aria-hidden="true" />
            )}
            Apply Settings
          </Button>
        </div>
      </form>
    </>
  );
}

function statusLabel(status: ProviderStatus) {
  switch (status) {
    case "configured":
      return "Configured";
    case "missing":
      return "Missing";
    case "tested":
      return "Tested";
    case "failed":
      return "Failed";
    default:
      return "Untested";
  }
}

function statusVariant(status: ProviderStatus) {
  switch (status) {
    case "tested":
      return "success" as const;
    case "configured":
      return "info" as const;
    case "failed":
      return "destructive" as const;
    case "missing":
      return "warning" as const;
    default:
      return "secondary" as const;
  }
}
