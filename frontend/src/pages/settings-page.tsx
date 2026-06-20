import { Save } from "lucide-react";
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

export function SettingsPage() {
  const [saved, setSaved] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(true);
  }

  return (
    <>
      <PageHeader
        eyebrow="Settings"
        title="Provider settings"
        description="Configure the model provider used for report generation."
      />

      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Analysis provider</CardTitle>
          <CardDescription>Credentials are intended to stay local.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-5" onSubmit={handleSubmit}>
            <div className="grid gap-2">
              <Label htmlFor="provider">Provider</Label>
              <Select id="provider" name="provider" defaultValue="openai">
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="local">Local model</option>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="model">Model</Label>
              <Input id="model" name="model" defaultValue="gpt-4.1-mini" />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="api-key">API key</Label>
              <Input
                autoComplete="off"
                id="api-key"
                name="api-key"
                placeholder="Stored by backend settings endpoint"
                type="password"
              />
            </div>

            <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center">
              <Button type="submit">
                <Save className="h-4 w-4" aria-hidden="true" />
                Save settings
              </Button>
              {saved ? (
                <p className="text-sm text-muted-foreground">
                  Settings saved locally in this session.
                </p>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  );
}
