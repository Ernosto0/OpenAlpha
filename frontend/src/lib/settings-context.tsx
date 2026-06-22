import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, type AppSettings } from "./api";

type SettingsContextValue = {
  settings: AppSettings | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  applySettings: (settings: AppSettings) => void;
};

const SettingsContext = createContext<SettingsContextValue | undefined>(undefined);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await api.getSettings();
      setSettings(data);
      setError(null);
    } catch {
      setError("Unable to load settings.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({
      settings,
      isLoading,
      error,
      refresh,
      applySettings: setSettings,
    }),
    [error, isLoading, refresh, settings],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useAppSettings() {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error("useAppSettings must be used within SettingsProvider");
  }
  return context;
}
